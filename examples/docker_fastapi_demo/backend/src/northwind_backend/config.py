from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
REFERENCE_DIR = PROJECT_DIR / "reference"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "northwind.sqlite"
DEFAULT_ADMIN_YAML_PATH = REFERENCE_DIR / "nw-admin.yaml"


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    swagger_host: str
    swagger_port: int
    api_prefix: str
    db_path: Path
    admin_yaml_path: Path
    docs_asset_dir: Path | None
    default_framework: str


def _resolve_path(value: str, default: Path) -> Path:
    return Path(value).expanduser().resolve() if value else default.resolve()


def _resolve_optional_path(value: str) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def get_settings() -> Settings:
    host = os.getenv("NORTHWIND_HOST", "127.0.0.1")
    port = int(os.getenv("NORTHWIND_PORT", "5656"))
    return Settings(
        host=host,
        port=port,
        swagger_host=os.getenv("NORTHWIND_SWAGGER_HOST", host),
        swagger_port=int(os.getenv("NORTHWIND_SWAGGER_PORT", str(port))),
        api_prefix=os.getenv("NORTHWIND_API_PREFIX", "/api"),
        db_path=_resolve_path(os.getenv("NORTHWIND_DB_PATH", ""), DEFAULT_DB_PATH),
        admin_yaml_path=_resolve_path(os.getenv("NORTHWIND_ADMIN_YAML_PATH", ""), DEFAULT_ADMIN_YAML_PATH),
        docs_asset_dir=_resolve_optional_path(os.getenv("NORTHWIND_DOCS_ASSET_DIR", "")),
        default_framework=os.getenv("NORTHWIND_BACKEND", "fastapi"),
    )
