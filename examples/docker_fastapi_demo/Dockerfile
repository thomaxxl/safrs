FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nginx nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY backend /app/backend
COPY examples /app/examples
COPY frontend /app/frontend
COPY reference /app/reference
COPY site /usr/share/nginx/html
COPY vendor /app/vendor
COPY nginx.conf /etc/nginx/sites-enabled/default
COPY entrypoint.sh /app/entrypoint.sh

WORKDIR /app/backend

RUN python -m pip install --no-cache-dir -U pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && chmod +x /app/entrypoint.sh

WORKDIR /app/frontend

RUN npm install --no-audit --no-fund --package-lock=false

WORKDIR /app

EXPOSE 80

CMD ["/app/entrypoint.sh"]
