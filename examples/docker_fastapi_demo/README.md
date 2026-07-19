# Demo Container

This directory packages the current Northwind validation app as a self-contained demo container:

- `backend/` is a copied FastAPI-capable SAFRS backend
- `frontend/` is the copied React frontend source run with `npm run dev`
- `reference/` contains the shipped `admin.yaml`
- `site/` contains the simple landing page served by nginx at `/`
- `vendor/safrs/` is a vendored copy of the current SAFRS source used by the backend image
- `vendor/safrs-jsonapi-client/` is an optional local fallback for the frontend client package

The container runs multiple processes:

- FastAPI backend on `127.0.0.1:5656`
- JWT example FastAPI SAFRS app on `127.0.0.1:5001`
- filtering example FastAPI SAFRS app on `127.0.0.1:5002`
- RPC example FastAPI SAFRS app on `127.0.0.1:5003`
- search example FastAPI SAFRS app on `127.0.0.1:5004`
- basic relationship example FastAPI SAFRS app on `127.0.0.1:5005`
- Vite dev server on `127.0.0.1:5173`
- nginx on port `80`, reverse proxying both of them from one origin

## Run

```bash
docker compose up --build
```

Then open:

- `http://localhost:8000/`

Landing page links:

- `/admin-app/` for the SPA
- `/docs` for the FastAPI docs
- `/api_demo_relationship/docs` for the basic relationship example docs
- `/api_demo_jwt/docs` for the JWT example docs
- `/api_ex06_filtering/docs` for the filtering example docs
- `/api_ex08_rpc/docs` for the RPC example docs
- `/api_ex11_search/docs` for the search example docs
- `/code/...` for plain-text example source files served by nginx

You can override the host port:

```bash
DEMO_PORT=9090 docker compose up --build
```

## Dev mode with host-mounted sources

The baked-in image uses files under `/app` inside the container.

For development, there is an optional override file that bind-mounts the entire
`demo/` directory to `/demo`:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  up --build
```

When `/demo` is mounted, the entrypoint switches the running processes to use
the host-mounted files from `/demo` instead of the copied files under `/app`.

That affects:

- `/demo/backend`
- `/demo/examples`
- `/demo/frontend`
- `/demo/reference`
- `/demo/site`
- `/demo/vendor/safrs`
- `/demo/vendor/safrs-jsonapi-client`

The dev override also keeps `/demo/frontend/node_modules` in a separate Docker
volume so the bind mount does not hide installed dependencies.

In dev mode, frontend dependencies are seeded from the baked image instead of
running `npm install` at container startup. The mounted
`vendor/safrs-jsonapi-client/` checkout is then linked into
`/demo/frontend/node_modules/safrs-jsonapi-client` by default.

In that mode, you can edit files under `demo/` on the host without rebuilding
the image. Frontend edits should be picked up by Vite. Backend, example-app,
nginx config, and vendored client/library changes usually require a container
restart, but not an image rebuild.

The dev override also enables FastAPI auto-reload for:

- the main Northwind backend
- the JWT example app
- the basic relationship example app
- the filtering example app
- the RPC example app
- the search example app

It does that by setting environment flags consumed by `entrypoint.sh` and
running the FastAPI apps under `uvicorn --reload`. Polling-based file watching
is also enabled for mounted files.

Container paths:

- default baked-in frontend: `/app/frontend`
- dev-mounted frontend: `/demo/frontend`

## Client dependency source

By default, the frontend installs `safrs-jsonapi-client` from:

- `git+https://github.com/thomaxxl/safrs-jsonapi-client.git#main`

In dev mode, local vendored fallback is enabled by default. To force local
vendored fallback in normal mode, set:

```bash
USE_LOCAL_SAFRS_JSONAPI_CLIENT=1 docker compose up --build
```

## Notes

- The runtime SQLite database is stored in the `northwind_demo_data` Docker volume.
- On first start, the container seeds that volume from `backend/data/northwind.sqlite`.
- The backend runs the FastAPI variant only in this demo package.
- The frontend is served by Vite dev server inside the container rather than by precompiled static assets.
- The first bundled example is `demo/examples/authentication/demo_jwt.py`, exposed under `/api_demo_jwt/`.
- In that example, `Items` are public and `Users` require a JWT bearer token obtained from `POST /api_demo_jwt/login`.
- Additional bundled FastAPI examples:
  - `demo/examples/demo_relationship.py` at `/api_demo_relationship/`
  - `demo/examples/mini_examples/ex06_filtering.py` at `/api_ex06_filtering/`
  - `demo/examples/mini_examples/ex08_rpc.py` at `/api_ex08_rpc/`
  - `demo/examples/mini_examples/ex11_search.py` at `/api_ex11_search/`
