FROM node:24-bookworm-slim AS node-runtime

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends git nginx \
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

RUN npm ci --no-audit --no-fund

WORKDIR /app

EXPOSE 80

CMD ["/app/entrypoint.sh"]
