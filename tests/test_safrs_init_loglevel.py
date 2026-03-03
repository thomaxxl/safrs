from __future__ import annotations

import logging

from safrs.safrs_init import _resolve_loglevel


def test_resolve_loglevel_prefers_loglevel_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LOGLEVEL", "10")
    monkeypatch.setenv("DEBUG", "0")
    monkeypatch.setenv("FLASK_DEBUG", "0")
    assert _resolve_loglevel() == logging.DEBUG


def test_resolve_loglevel_uses_debug_numeric_value_when_loglevel_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert _resolve_loglevel() == 1


def test_resolve_loglevel_uses_debug_truthy_as_logging_debug(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert _resolve_loglevel() == logging.DEBUG


def test_resolve_loglevel_uses_flask_debug_when_loglevel_and_debug_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert _resolve_loglevel() == logging.DEBUG


def test_resolve_loglevel_default_warning(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert _resolve_loglevel() == logging.WARNING
