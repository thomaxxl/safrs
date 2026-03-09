from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from uuid import uuid4


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_example(module_filename: str) -> ModuleType:
    module_path = EXAMPLES_DIR / module_filename
    module_name = f"example_{module_path.stem}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mini_fastapi_app_debug_env_enables_debug_and_reload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_example("mini_fastapi_app.py")
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("SAFRS_DISABLE_RELOAD", raising=False)
    assert module._resolve_log_level() <= logging.DEBUG
    assert module._debug_enabled() is True
    assert module._reload_enabled() is True


def test_mini_fastapi_app_reload_can_be_forced_off(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_example("mini_fastapi_app.py")
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("SAFRS_DISABLE_RELOAD", "1")
    assert module._reload_enabled() is False


def test_mini_app_debug_env_enables_debug_and_reload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_example("mini_app.py")
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("SAFRS_DISABLE_RELOAD", raising=False)
    assert module._resolve_log_level() <= logging.DEBUG
    assert module._debug_enabled() is True
    assert module._reload_enabled() is True


def test_mini_app_reload_can_be_forced_off(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_example("mini_app.py")
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("SAFRS_DISABLE_RELOAD", "1")
    assert module._reload_enabled() is False
