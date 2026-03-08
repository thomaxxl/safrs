# Northwind Backend

This backend contains two SAFRS app variants over the same Northwind model layer:

- a Flask app using `SafrsApi`
- a FastAPI app using `SafrsFastAPI`

They exist side by side so the same validation project can be used to compare consumer-facing behavior easily.

## Current intent

- both backends use the same SQLite database
- both backends expose the same resource and relationship names as the Northwind `admin.yaml`
- both backends use the same `admin.yaml`
- both backends are intended to run on port `5656`

The main SAFRS development track is FastAPI, but Flask remains the reference behavior. This project supports switching between them quickly.

## Quick start

Create a virtual environment, install the requirements, and run one backend variant from this directory:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py fastapi
```

Or:

```bash
python run.py flask
```

Default URL targets for both variants:

- API root: `http://127.0.0.1:5656/api`
- Admin schema: `http://127.0.0.1:5656/ui/admin/admin.yaml`

## Switching

Use one process at a time on the same port:

- `python run.py fastapi`
- `python run.py flask`

You can also override host and port:

```bash
python run.py fastapi --host 127.0.0.1 --port 5656
python run.py flask --host 127.0.0.1 --port 5656
```

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

The active validation focus is no longer basic exposure. It is parity: the Flask and FastAPI apps should both honor the same documented contract and accept the same consumer-facing include paths.
