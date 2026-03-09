from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_exposes_fastapi_and_flask_extras() -> None:
    pyproject_path = Path("pyproject.toml")
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    base_deps = set(pyproject["project"]["dependencies"])
    extras = pyproject["project"]["optional-dependencies"]

    assert "fastapi" in extras
    assert "flask" in extras
    assert "fastapi[standard]>=0.135.1" in extras["fastapi"]
    assert "flask-restful-swagger-2>=0.35" in extras["flask"]
    assert "fastapi[standard]>=0.135.1" in base_deps
    assert "flask-restful-swagger-2>=0.35" in base_deps


def test_setup_py_defines_matching_adapter_extras() -> None:
    setup_py = Path("setup.py").read_text(encoding="utf-8")
    assert '"flask": flask_extra' in setup_py
    assert '"fastapi": fastapi_extra' in setup_py
    assert '"all": flask_extra + fastapi_extra' in setup_py
