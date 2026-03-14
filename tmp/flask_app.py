from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import models  # noqa: F401


_APPS_DIR = Path(__file__).resolve().parents[2] / "verifier" / "apps"
_MODULE_PATH = _APPS_DIR / "flask_app.py"
_MODULE_NAME = "_safrs_tmp_verifier_flask_app"
_TMP_DIR = Path(__file__).resolve().parent


def _load_flask_module() -> object:
    module = sys.modules.get(_MODULE_NAME)
    if module is not None:
        return module

    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load verifier flask app from {_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _tmp_reset_enabled() -> str:
    value = os.environ.get("SAFRS_TMP_RESET_DB")
    if value is None:
        return "1"
    return value


def _resolve_tmp_db_path(port: int, db_name: str | None = None) -> Path:
    db_dir_raw = os.environ.get("SAFRS_TMP_DB_DIR", "").strip()
    db_dir = Path(db_dir_raw).expanduser() if db_dir_raw else _TMP_DIR

    filename = db_name or os.environ.get("SAFRS_TMP_DB", "").strip() or f"tmp_flask_{port}.db"
    path = Path(filename).expanduser()
    if not path.is_absolute():
        path = (db_dir / path).resolve()
    return path


@contextmanager
def _mapped_tmp_environment(db_path: Path) -> Iterator[None]:
    env_updates = {
        "SAFRS_EXAMPLE_DB_PATH": str(db_path),
        "SAFRS_EXAMPLE_RESET_DB": _tmp_reset_enabled(),
    }
    previous = {key: os.environ.get(key) for key in env_updates}
    try:
        for key, value in env_updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def create_app(host: str = "127.0.0.1", port: int = 5000, db_name: str | None = None) -> Any:
    impl = _load_flask_module()
    db_path = _resolve_tmp_db_path(port=port, db_name=db_name)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _mapped_tmp_environment(db_path):
        return impl.create_app(host=host, port=port)


if __name__ == "__main__":
    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    app = create_app(host=bind_host, port=bind_port)
    app.run(host=bind_host, port=bind_port, threaded=False, debug=False, use_reloader=False)
