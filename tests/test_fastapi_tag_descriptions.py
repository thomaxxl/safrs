from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from safrs import SAFRSBase
from safrs.fastapi.api import SafrsFastAPI


class _UndocumentedModel(SAFRSBase):
    _s_type = "Thing"
    _s_collection_name = "Things"


class _DocumentedModel(SAFRSBase):
    """
    description: Explicit model description
    """

    _s_type = "Widget"
    _s_collection_name = "Widgets"


def test_model_tag_description_does_not_inherit_safrsbase_docstring() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app)

    assert api._model_tag_description(_UndocumentedModel, "Things") == "Things operations"


def test_model_tag_description_uses_model_raw_docstring() -> None:
    app = FastAPI()
    api = SafrsFastAPI(app)

    assert api._model_tag_description(_DocumentedModel, "Widgets") == "description: Explicit model description"


def test_safrs_fastapi_installs_swagger_ui_defaults() -> None:
    app = FastAPI()

    SafrsFastAPI(app)

    assert app.swagger_ui_parameters["docExpansion"] == "none"
    assert app.swagger_ui_parameters["defaultModelsExpandDepth"] == -1


def test_safrs_fastapi_preserves_existing_swagger_ui_parameters() -> None:
    app = FastAPI(swagger_ui_parameters={"docExpansion": "full", "persistAuthorization": True})

    SafrsFastAPI(app)

    assert app.swagger_ui_parameters["docExpansion"] == "full"
    assert app.swagger_ui_parameters["defaultModelsExpandDepth"] == -1
    assert app.swagger_ui_parameters["persistAuthorization"] is True
