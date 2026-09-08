from __future__ import annotations

import json
import tracemalloc

import pytest
from sqlalchemy import Column, Integer, create_engine, event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base

from perf_telemetry import Sample, measure, summarize


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    yield engine
    engine.dispose()


def test_counts_parameterized_queries_without_recording_sql_or_parameters(engine):
    def request():
        with engine.connect() as conn:
            for secret in ("private-one", "private-two"):
                assert conn.scalar(text("SELECT :value"), {"value": secret}) == secret
            assert conn.scalar(text("SELECT count(*) FROM (SELECT 1)")) == 1
        return b'{"data": []}'

    sample, body = measure(engine, request)
    assert sample.sql_count == 3
    assert sample.count_queries == 1
    assert sample.repeated_sql == 1
    assert sample.response_bytes == len(body)
    assert sample.orm_loads == 0
    assert sample.wall_ms >= sample.sql_ms >= 0
    assert sample.cpu_ms >= 0
    assert sample.peak_python_bytes is None
    encoded = json.dumps(summarize([sample]))
    assert "private" not in encoded and "SELECT" not in encoded
    # A second sample must neither accumulate counters nor inherit listeners.
    second, _ = measure(engine, request)
    assert second.sql_count == 3
    assert sample.sql_count == 3


def test_orm_loads_count_hydration_only_on_the_measured_engine(engine):
    Base = declarative_base()

    class Row(Base):
        __tablename__ = "telemetry_rows"
        id = Column(Integer, primary_key=True)

    other = create_engine("sqlite://")
    for target in (engine, other):
        Base.metadata.create_all(target)
        with target.begin() as conn:
            conn.execute(Row.__table__.insert(), [{"id": 1}, {"id": 2}])

    def request():
        with Session(engine) as session, Session(other) as unrelated:
            rows = session.scalars(select(Row)).all()
            assert len(rows) == len(unrelated.scalars(select(Row)).all()) == 2
            assert session.get(Row, 1) is rows[0]
        return b"{}"

    try:
        sample, _ = measure(engine, request)
        assert sample.sql_count == 1
        assert sample.orm_loads == 2
    finally:
        other.dispose()


@pytest.mark.parametrize("sql_failure", [False, True])
def test_failure_removes_listeners_and_stops_owned_memory_tracing(engine, sql_failure):
    external = []

    def existing_listener(*args):
        external.append(True)

    event.listen(engine, "before_cursor_execute", existing_listener)

    def fail():
        with engine.connect() as conn:
            conn.execute(text("SELECT * FROM missing_table" if sql_failure else "SELECT 1"))
        raise ValueError("application failed")

    try:
        with pytest.raises(OperationalError if sql_failure else ValueError):
            measure(engine, fail, memory=True)
        assert not tracemalloc.is_tracing()
        assert event.contains(engine, "before_cursor_execute", existing_listener)
        assert len(engine.dispatch.before_cursor_execute) == 1
        assert len(engine.dispatch.after_cursor_execute) == 0
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        assert len(external) == 2
    finally:
        event.remove(engine, "before_cursor_execute", existing_listener)


def test_memory_mode_reports_python_allocations(engine):
    sample, body = measure(engine, lambda: b"x" * 100_000, memory=True)
    assert sample.peak_python_bytes >= len(body)
    assert sample.sql_count == 0
    assert not tracemalloc.is_tracing()


def test_existing_tracer_is_preserved(engine):
    tracemalloc.start()
    try:
        with pytest.raises(RuntimeError, match="existing tracemalloc"):
            measure(engine, lambda: b"{}", memory=True)
        measure(engine, lambda: b"{}")
        assert tracemalloc.is_tracing()
        assert len(engine.dispatch.before_cursor_execute) == 0
    finally:
        tracemalloc.stop()


def test_summary_preserves_raw_samples_and_uses_nearest_rank_p95():
    samples = [Sample(wall_ms=float(n), sql_count=n) for n in range(1, 21)]
    summary = summarize(list(reversed(samples)))
    assert summary["wall_p50_ms"] == 10.5
    assert summary["wall_p95_ms"] == 19
    assert summary["sql_count_max"] == 20
    assert len(summary["samples"]) == 20
    assert summarize([Sample(wall_ms=3)])["wall_p95_ms"] == 3
    with pytest.raises(ValueError, match="At least one"):
        summarize([])
