# safrs-jsonapi-client

Phase-1 scaffold for a SAFrs/ApiLogicServer JSON:API client with a React-admin adapter.

## Status

Initial implementation includes:
- schema normalization from `admin.yaml`
- `api_root` resolution
- pure query builders
- transport with JSON:API error mapping
- document normalization + shallow hydration
- total extraction (`meta.count` -> `meta.total` -> `data.length`)
- write sanitization
- React-admin-style data provider adapter
- `updateMany` / `deleteMany` bulk fallbacks
- CLI smoke runner

Backlog in base milestone:
- `filter.q` semantics (currently ignored with warning)

## Install

```bash
npm install
```

## Build

```bash
npm run build
```

## Test

```bash
npm test
```

Integration tests (real API):

```bash
RUN_INTEGRATION=1 API_URL=http://localhost:8000/api/ ADMIN_YAML_URL=http://localhost:8000/ui/admin/admin.yaml npm run test:integration
```

## Smoke test

```bash
node dist/cli/smoke.js --admin-yaml /path/to/admin.yaml --api-url https://your-api.example.com/api/ --resource YourResource --limit 1
```

`--resource` is optional. If omitted, the smoke runner uses the first resource found in `admin.yaml`.
`--admin-yaml` accepts either a local path or an `http(s)` URL.

Or:

```bash
npm run smoke -- --admin-yaml /path/to/admin.yaml --api-url https://your-api.example.com/api/ --resource YourResource --limit 1
```

## Fixtures

Fetch/update response fixtures from a live API:

```bash
npm run fixtures:fetch -- --baseUrl http://localhost:8000/api/ --resource Order --id 10248 --include Customer,Employee
```

## Usage

```ts
import { createDataProvider } from 'safrs-jsonapi-client';

const dataProvider = await createDataProvider({
  adminYamlUrl: '/ui/admin/admin.yaml',
  apiRoot: 'https://your-api.example.com/api/'
});
```
