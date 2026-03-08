from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from northwind_backend import create_fastapi_app, create_flask_app
from northwind_backend.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Northwind SAFRS backend.")
    parser.add_argument(
        "framework",
        nargs="?",
        choices=("fastapi", "flask"),
        help="Backend implementation to run. Defaults to NORTHWIND_BACKEND or fastapi.",
    )
    parser.add_argument("--host", help="Bind host override.")
    parser.add_argument("--port", type=int, help="Bind port override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    framework = (args.framework or settings.default_framework).lower()
    host = args.host or settings.host
    port = args.port or settings.port

    if framework == "fastapi":
        import uvicorn

        uvicorn.run(create_fastapi_app(), host=host, port=port, log_level="info")
        return

    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.wsgi import WSGIMiddleware

    flask_runner = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    flask_runner.mount("/", WSGIMiddleware(create_flask_app()))
    uvicorn.run(flask_runner, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
