from __future__ import annotations

from .config import get_settings
from .fastapi_app import create_fastapi_app
from .flask_app import create_flask_app


def create_app(framework: str | None = None):
    resolved_framework = (framework or get_settings().default_framework).lower()
    if resolved_framework == "fastapi":
        return create_fastapi_app()
    if resolved_framework == "flask":
        return create_flask_app()
    raise ValueError(f"Unknown backend framework: {resolved_framework}")
