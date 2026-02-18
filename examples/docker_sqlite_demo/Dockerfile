# SQLite-only SAFRS demo container (no DB containers)
#
# Build context is expected to be the SAFRS repo root (../../ from this folder)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy the SAFRS repo into the image
COPY . .

# Install dependencies + SAFRS itself (editable install so local code changes work with a bind mount)
RUN python -m pip install --no-cache-dir -U pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir gunicorn \
    && python -m pip install --no-cache-dir -e .

# Keep the SQLite db outside of the code tree
VOLUME ["/data"]

EXPOSE 80

# Use `sh` so the script doesn't need the executable bit on all host OSes
CMD ["sh", "/app/examples/docker_sqlite_demo/entrypoint.sh"]
