"""Test-only telemetry for serial, in-process requests; no runtime hooks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import hashlib
import math
import re
import statistics
import time
import tracemalloc
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


@dataclass
class Sample:
    wall_ms: float = 0.0
    cpu_ms: float = 0.0
    sql_ms: float = 0.0
    sql_count: int = 0
    count_queries: int = 0
    repeated_sql: int = 0
    orm_loads: int = 0
    response_bytes: int = 0
    peak_python_bytes: int | None = None


def measure(engine: Engine, operation: Callable[[], bytes], *, memory: bool = False) -> tuple[Sample, bytes]:
    """Measure through response rendering, excluding fixture setup and parsing.

    Cursor execution time excludes fetching rows and ORM hydration. SQL shapes
    are hashed in memory to count repetition; neither SQL nor parameters are
    emitted. Listeners and optional tracing are removed even on exceptions.
    Memory mode is a separate diagnostic run because tracing distorts latency.
    """
    if memory and tracemalloc.is_tracing():
        raise RuntimeError("Run performance memory telemetry without an existing tracemalloc session")
    sample = Sample()
    starts: dict[int, int] = {}
    shapes: Counter[str] = Counter()

    def before(_conn: Any, _cursor: Any, statement: str, _params: Any, context: Any, _many: bool) -> None:
        sample.sql_count += 1
        sample.count_queries += int(bool(re.search(r"\bcount\s*\(", statement, re.IGNORECASE)))
        shapes[hashlib.sha256(" ".join(statement.split()).encode()).hexdigest()] += 1
        starts[id(context)] = time.perf_counter_ns()

    def after(_conn: Any, _cursor: Any, _statement: str, _params: Any, context: Any, _many: bool) -> None:
        sample.sql_ms += (time.perf_counter_ns() - starts.pop(id(context))) / 1_000_000

    def loaded(session: Session, instance: Any) -> None:
        if session.get_bind(mapper=type(instance)) is engine:
            sample.orm_loads += 1

    listeners = [
        (engine, "before_cursor_execute", before),
        (engine, "after_cursor_execute", after),
        (Session, "loaded_as_persistent", loaded),
    ]
    installed = []
    try:
        for target, name, listener in listeners:
            event.listen(target, name, listener)
            installed.append((target, name, listener))
        if memory:
            tracemalloc.start()
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        body = operation()
        sample.cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
        sample.wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
        sample.response_bytes = len(body)
        sample.repeated_sql = sum(count - 1 for count in shapes.values())
        if memory:
            sample.peak_python_bytes = tracemalloc.get_traced_memory()[1]
        return sample, body
    finally:
        if memory and tracemalloc.is_tracing():
            tracemalloc.stop()
        for target, name, listener in reversed(installed):
            event.remove(target, name, listener)


def summarize(samples: Sequence[Sample]) -> dict[str, Any]:
    if not samples:
        raise ValueError("At least one performance sample is required")
    walls = sorted(sample.wall_ms for sample in samples)
    return {
        "samples": [asdict(sample) for sample in samples],
        "wall_p50_ms": statistics.median(walls),
        "wall_p95_ms": walls[math.ceil(0.95 * len(walls)) - 1],
        "cpu_p50_ms": statistics.median(sample.cpu_ms for sample in samples),
        "sql_p50_ms": statistics.median(sample.sql_ms for sample in samples),
        "sql_count_max": max(sample.sql_count for sample in samples),
        "count_queries_max": max(sample.count_queries for sample in samples),
        "repeated_sql_max": max(sample.repeated_sql for sample in samples),
        "orm_loads_max": max(sample.orm_loads for sample in samples),
        "response_bytes_max": max(sample.response_bytes for sample in samples),
    }
