# Northwind Backend

This backend is the FastAPI SAFRS backend used by the demo container.

It can also be run standalone from this directory with `run.py`.

## Current intent

- the demo container uses the FastAPI variant only
- the backend uses the Northwind SQLite database
- it exposes the same resource and relationship names as the shipped Northwind `admin.yaml`
- it serves the same `admin.yaml` used by the frontend
- the default standalone port is `5656`

## Run standalone

From this directory:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Because `requirements.txt` contains `-e ../vendor/safrs`, run `pip install -r requirements.txt` from the `backend/` directory so that relative path resolves correctly.

`python run.py` defaults to the FastAPI app.

You can also override host and port:

```bash
python run.py fastapi --host 127.0.0.1 --port 5656
```

Default URL targets:

- API root: `http://127.0.0.1:5656/api`
- docs: `http://127.0.0.1:5656/docs`
- OpenAPI: `http://127.0.0.1:5656/jsonapi.json`
- Admin schema: `http://127.0.0.1:5656/ui/admin/admin.yaml`

## Current scope

The backend now exposes the full resource set currently described in `reference/nw-admin.yaml`:

- `Category`
- `Customer`
- `CustomerDemographic`
- `Department`
- `Employee`
- `EmployeeAudit`
- `EmployeeTerritory`
- `Location`
- `Order`
- `OrderDetail`
- `Product`
- `Region`
- `SampleDBVersion`
- `Shipper`
- `Supplier`
- `Territory`
- `Union`

The active validation focus is consumer-facing parity and behavior validation against the frontend and example clients.
