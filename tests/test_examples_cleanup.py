from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"


def _iter_example_sources() -> list[Path]:
    return sorted(
        path
        for path in EXAMPLES_DIR.rglob("*.py")
        if "__pycache__" not in path.parts and ".pytest_cache" not in path.parts
    )


def _module_function_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in module.body if isinstance(node, ast.FunctionDef)}


def test_examples_have_valid_python_syntax() -> None:
    for path in _iter_example_sources():
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def test_supported_examples_expose_create_app() -> None:
    supported = [
        EXAMPLES_DIR / "mini_app.py",
        EXAMPLES_DIR / "mini_fastapi_app.py",
        EXAMPLES_DIR / "demo_relationship.py",
        EXAMPLES_DIR / "demo_fastapi.py",
        EXAMPLES_DIR / "demo_pythonanywhere_com.py",
        EXAMPLES_DIR / "demo_http_get.py",
        EXAMPLES_DIR / "demo_http_method.py",
        EXAMPLES_DIR / "demo_stateless.py",
        EXAMPLES_DIR / "authentication" / "demo_auth.py",
        EXAMPLES_DIR / "authentication" / "demo_jwt.py",
        EXAMPLES_DIR / "authentication" / "demo_post_auth.py",
    ]
    for path in supported:
        assert "create_app" in _module_function_names(path), f"missing create_app in {path}"


def test_demo_full_is_compatibility_wrapper() -> None:
    source = (EXAMPLES_DIR / "demo_full.py").read_text(encoding="utf-8")
    assert "demo_pythonanywhere_com" in source
    assert "Compatibility wrapper" in source

