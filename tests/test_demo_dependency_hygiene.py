from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging.version import Version


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = REPO_ROOT / "examples" / "docker_fastapi_demo"
FRONTEND_ROOT = DEMO_ROOT / "frontend"
VENDOR_ROOT = DEMO_ROOT / "vendor" / "safrs-jsonapi-client"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _locked_versions(lock: dict[str, Any], package_name: str) -> set[Version]:
    suffix = f"node_modules/{package_name}"
    return {
        Version(details["version"])
        for path, details in lock["packages"].items()
        if path == suffix or path.endswith(f"/{suffix}")
    }


def test_frontend_lock_matches_manifest_and_uses_https_git_sources() -> None:
    manifest = _read_json(FRONTEND_ROOT / "package.json")
    lock = _read_json(FRONTEND_ROOT / "package-lock.json")
    lock_root = lock["packages"][""]

    assert lock_root["dependencies"] == manifest["dependencies"]
    assert lock_root["devDependencies"] == manifest["devDependencies"]

    git_sources = [
        details["resolved"]
        for details in lock["packages"].values()
        if str(details.get("resolved", "")).startswith("git+")
    ]
    assert git_sources
    assert all(source.startswith("git+https://") for source in git_sources)


def test_frontend_lock_keeps_security_fixed_dependency_floors() -> None:
    lock = _read_json(FRONTEND_ROOT / "package-lock.json")
    minimum_versions = {
        "@vitejs/plugin-react": Version("6.0.2"),
        "dompurify": Version("3.4.11"),
        "lodash": Version("4.18.1"),
        "picomatch": Version("4.0.4"),
        "postcss": Version("8.5.14"),
        "react-admin": Version("5.14.6"),
        "react-router": Version("7.18.0"),
        "react-router-dom": Version("7.18.0"),
        "vite": Version("8.0.16"),
        "yaml": Version("2.8.3"),
    }

    for package_name, minimum_version in minimum_versions.items():
        versions = _locked_versions(lock, package_name)
        assert versions, f"{package_name} is missing from the frontend lock"
        assert min(versions) >= minimum_version

    assert _locked_versions(lock, "@babel/core") == set()
    assert _locked_versions(lock, "esbuild") == set()


def test_vendored_client_lock_contains_only_runtime_dependencies() -> None:
    manifest = _read_json(VENDOR_ROOT / "package.json")
    lock = _read_json(VENDOR_ROOT / "package-lock.json")
    lock_root = lock["packages"][""]

    assert lock_root["dependencies"] == manifest["dependencies"]
    assert "devDependencies" not in lock_root
    assert all(not details.get("dev", False) for details in lock["packages"].values())
    assert min(_locked_versions(lock, "yaml")) >= Version("2.8.3")


def test_demo_container_installs_the_audited_frontend_lock() -> None:
    dockerfile = (DEMO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (DEMO_ROOT / "entrypoint.sh").read_text(encoding="utf-8")

    assert "npm ci --no-audit --no-fund" in dockerfile
    assert "npm ci --no-audit --no-fund" in entrypoint
    assert "--package-lock=false" not in dockerfile
    assert "--package-lock=false" not in entrypoint
