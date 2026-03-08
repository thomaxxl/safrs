from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from safrs.fastapi import SafrsFastAPI

from .config import get_settings
from .db import create_runtime
from .models import EXPOSED_MODELS, EXPOSED_RESOURCE_NAMES


def create_fastapi_app() -> FastAPI:
    settings = get_settings()
    runtime = create_runtime(settings.db_path)

    app = FastAPI(
        title="Northwind SAFRS FastAPI Validation App",
        docs_url=None,
        redoc_url=None,
        openapi_url="/jsonapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _remove_session_middleware(request, call_next):
        try:
            return await call_next(request)
        finally:
            runtime.session.remove()

    api = SafrsFastAPI(app, prefix=settings.api_prefix)
    app.state.safrs_api = api
    app.state.safrs_runtime = runtime

    docs_asset_dir = settings.docs_asset_dir
    if docs_asset_dir and docs_asset_dir.is_dir():
        app.mount("/docs-assets", StaticFiles(directory=str(docs_asset_dir)), name="docs-assets")

    for model in EXPOSED_MODELS:
        api.expose_object(model)

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/docs", status_code=307)

    @app.get("/docs", include_in_schema=False)
    def docs() -> object:
        docs_kwargs: dict[str, object] = {
            "openapi_url": app.openapi_url or "/jsonapi.json",
            "title": f"{app.title} - Swagger UI",
            "swagger_ui_parameters": app.swagger_ui_parameters,
        }
        if docs_asset_dir and docs_asset_dir.is_dir():
            docs_kwargs.update(
                swagger_js_url="/docs-assets/swagger-ui-bundle.js",
                swagger_css_url="/docs-assets/swagger-ui.css",
                swagger_favicon_url="/docs-assets/favicon.svg",
            )
        return get_swagger_ui_html(
            **docs_kwargs,
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "framework": "fastapi",
            "port": settings.port,
            "api_prefix": settings.api_prefix,
        }

    @app.get("/ui/admin/admin.yaml", include_in_schema=False)
    def admin_yaml() -> FileResponse:
        return FileResponse(settings.admin_yaml_path, media_type="text/yaml")

    @app.get(f"{settings.api_prefix}/jsonapi.json", include_in_schema=False)
    def jsonapi_json_alias() -> dict[str, object]:
        return app.openapi()

    @app.get(f"{settings.api_prefix}/swagger.json", include_in_schema=False)
    def swagger_json_alias() -> dict[str, object]:
        return app.openapi()

    return app
