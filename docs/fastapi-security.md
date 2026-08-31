# FastAPI security dependencies

The FastAPI adapter uses FastAPI's native dependency injection for
authentication and authorization. Pass `Depends(...)` or `Security(...)` to
`SafrsFastAPI` to protect every exposed model:

```python
from fastapi import Depends, FastAPI, HTTPException, Request

from safrs.fastapi import SafrsFastAPI


def require_user(request: Request) -> None:
    if request.headers.get("authorization") != "Bearer example-token":
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI()
api = SafrsFastAPI(
    app,
    prefix="/api",
    dependencies=[Depends(require_user)],
)
api.expose_object(User)
api.expose_object(Book)
```

Constructor dependencies run for every generated collection, instance,
relationship, and RPC route. To protect one model instead, pass dependencies
when exposing it:

```python
api = SafrsFastAPI(app, prefix="/api")
api.expose_object(
    User,
    dependencies=[Depends(require_user)],
)
```

Per-model dependencies are also applied to routes for models that can expose
that model through a relationship. This prevents a less-restricted parent
resource from bypassing the target model's policy through relationship links,
compound `include` responses, or relationship data in create requests. Model
exposure order does not affect this propagation.

Use `Security(...)` in the same positions when the dependency needs OAuth2
scopes or another FastAPI security scheme:

```python
from fastapi import Security

api.expose_object(
    User,
    dependencies=[Security(require_user, scopes=["users:read"])],
)
```

`Model.decorators` and Flask `method_decorators` are not supported by the
FastAPI adapter. A model with a non-empty `decorators` list is rejected during
route registration. Move that authorization logic into a FastAPI dependency.
The Flask adapter continues to support model decorators.
