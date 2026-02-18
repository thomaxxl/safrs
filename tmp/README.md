# tmp demo apps

Shared SAFRS models are defined in `models.py`, then reused by:
- `flask_app.py` (Flask + `SAFRSAPI`)
- `fastapi_app.py` (FastAPI + `SafrsFastAPI`)

Run both from this directory:

```bash
cd /home/t/lab/safrs-example/safrs/tmp
python flask_app.py 127.0.0.1 5000
```

```bash
cd /home/t/lab/safrs-example/safrs/tmp
python fastapi_app.py 127.0.0.1 8000
```

Useful URLs:
- Flask API root: `http://127.0.0.1:5000/api`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- FastAPI OpenAPI: `http://127.0.0.1:8000/swagger.json`
- Health checks: `/health`
