# NW Demo CLI

Demo script for exercising JSON:API endpoints using `demos/nw/admin.yaml`.

## Run

```bash
npm run build
npm run demo:nw -- --api-url http://127.0.0.1:5000/api
```

## Current request

The first implemented request is:
- `getList("Customer")`
- `page=1`
- `page[limit]=10`

## Useful flags

```bash
node demos/nw/cli.cjs --help
```

- `--admin-yaml <path>`: defaults to `demos/nw/admin.yaml`
- `--api-url <url>`: API root override (`--api-root` alias also supported)
- `--resource <name>`: defaults to `Customer`
- `--page <n>`: defaults to `1`
- `--limit <n>`: defaults to `10`
