from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
from typing import Any

import pytest
from sqlalchemy.engine import Engine

from perf_telemetry import Sample, measure, summarize


REPORTS = pytest.StashKey[list[dict[str, Any]]]()


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ValueError("must be at least 1")
    return number


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("performance telemetry")
    group.addoption("--perf-samples", type=positive_int, default=5, help="Measured requests after one warmup (default: 5)")
    group.addoption("--perf-report", help="Write raw samples and environment metadata to a JSON file")
    group.addoption("--perf-memory", action="store_true", help="Trace Python allocations; timings will be distorted")


def pytest_configure(config: pytest.Config) -> None:
    config.stash[REPORTS] = []


@dataclass
class Observation:
    samples: list[Sample]
    payload: dict[str, Any]


@pytest.fixture
def observe(request: pytest.FixtureRequest, record_property: Callable[..., None]) -> Callable[..., Observation]:
    def run(engine: Engine, operation: Callable[[], bytes], reset: Callable[[], None], **workload: Any) -> Observation:
        reset()
        operation()  # Warm framework/SQL compilation caches, never the identity map.
        samples = []
        body = b""
        for _ in range(request.config.getoption("--perf-samples")):
            reset()
            sample, body = measure(engine, operation, memory=request.config.getoption("--perf-memory"))
            samples.append(sample)
        row = {"test": request.node.nodeid, "workload": workload, **summarize(samples)}
        request.config.stash[REPORTS].append(row)
        record_property("performance", json.dumps(row, sort_keys=True))
        return Observation(samples, json.loads(body))

    return run


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Any:
    outcome = yield
    report = outcome.get_result()
    if report.when in {"call", "teardown"}:
        for row in item.config.stash[REPORTS]:
            if row["test"] == item.nodeid and (report.when == "call" or report.failed):
                row["outcome"] = report.outcome


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    destination = session.config.getoption("--perf-report")
    if not destination:
        return
    import safrs

    package_path = Path(safrs.__file__).resolve()
    source_hash = hashlib.sha256()
    for source in sorted(package_path.parent.rglob("*.py")):
        source_hash.update(str(source.relative_to(package_path.parent)).encode())
        source_hash.update(b"\0")
        source_hash.update(source.read_bytes())
    revision = subprocess.run(
        ["git", "-C", str(package_path.parent), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=False,
    )
    report = {
        "schema_version": 1,
        "exitstatus": int(exitstatus),
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version,
            "packages": {name: version(name) for name in ("SQLAlchemy", "Flask", "fastapi", "pytest")},
            "safrs_path": str(package_path),
            "safrs_revision": revision.stdout.strip() if revision.returncode == 0 else None,
            "safrs_source_sha256": source_hash.hexdigest(),
            "memory_tracing": session.config.getoption("--perf-memory"),
            "warmups": 1, "samples": session.config.getoption("--perf-samples"),
        },
        "results": session.config.stash[REPORTS],
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def pytest_terminal_summary(terminalreporter: Any, config: pytest.Config) -> None:
    rows = config.stash[REPORTS]
    if not rows:
        return
    terminalreporter.section("Synchronous performance telemetry (informational timings)")
    terminalreporter.write_line("case | p50 ms | p95 ms | SQL | COUNT | ORM loads | bytes")
    for row in rows:
        terminalreporter.write_line(
            f"{row['test'].split('::')[-1]} | {row['wall_p50_ms']:.2f} | {row['wall_p95_ms']:.2f}"
            f" | {row['sql_count_max']} | {row['count_queries_max']}"
            f" | {row['orm_loads_max']} | {row['response_bytes_max']}"
        )
