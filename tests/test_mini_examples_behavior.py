from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4


MINI_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "mini_examples"


def _load_mini_example(module_filename: str) -> ModuleType:
    module_path = MINI_EXAMPLES_DIR / module_filename
    module_name = f"mini_example_{module_path.stem}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ex05_secret_relationship_does_not_expose_secretdata_in_swagger() -> None:
    module = _load_mini_example("ex05_secret_relationship.py")
    app = module.create_app(host="127.0.0.1")
    client = app.test_client()

    response = client.get("/swagger.json")
    assert response.status_code == 200
    swagger = response.get_json()
    assert isinstance(swagger, dict)

    paths = swagger.get("paths", {})
    definitions = swagger.get("definitions", {})

    assert isinstance(paths, dict)
    assert isinstance(definitions, dict)
    assert not any("secret" in str(path).lower() for path in paths.keys())
    assert not any("SecretData" in str(model_name) for model_name in definitions.keys())


def test_ex15_http_hook_uses_s_post_for_create() -> None:
    module = _load_mini_example("ex15_http_hook.py")
    app = module.create_app(host="127.0.0.1")
    client = app.test_client()

    captured_calls: list[dict[str, Any]] = []

    @classmethod
    def _wrapped_s_post(cls: Any, *args: Any, **kwargs: Any) -> Any:
        captured_calls.append(dict(kwargs))
        instance = cls(id=98765, **kwargs)
        module.db.session.add(instance)
        module.db.session.flush()
        return instance

    module.User._s_post = _wrapped_s_post
    payload = {"data": {"type": "User", "attributes": {"name": "hook-user", "email": "hook@example.com"}}}
    headers = {"Content-Type": "application/vnd.api+json", "Accept": "application/vnd.api+json"}

    response = client.post("/Users/", json=payload, headers=headers)
    assert response.status_code == 201
    assert len(captured_calls) == 1
    assert captured_calls[0]["name"] == "hook-user"
    assert captured_calls[0]["email"] == "hook@example.com"

