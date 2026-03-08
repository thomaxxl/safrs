# Northwind Frontend

This is the React-admin frontend validation app for the Northwind pilot.

It uses `safrs-jsonapi-client` as the data-provider layer and keeps resource
pages resource-specific, even though the rendering is still schema-driven from
`admin.yaml`.

## Current scope

The frontend now registers every resource described in `admin.yaml`:

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

The shared builders now live in the shared runtime at `frontend-generator/runtime`.

The Northwind frontend keeps thin local entry files and points at that shared runtime. Relevant local files are:

- `src/admin/resourceMetadata.ts`
- `src/admin/schemaDrivenViews.tsx`
- `src/resources.tsx`
- `src/shared-runtime`

The page structure is intended to stay editable:

- `admin.yaml` changes should mostly flow through the shared schema-driven helpers
- shared UI changes should be made in `frontend-generator/runtime`
- future generated frontends should pick up those shared changes without reimplementing them

## Current metadata support

The frontend now uses more of the admin metadata contract:

- attribute `label`
- attribute visibility controls such as `hidden`, `hide_list`, `hide_show`,
  and `hide_edit`
- resource and global `max_list_columns`
- `tab_groups` for relationship tabs on show pages

Relationship rendering is intentionally simpler than `safrs-react-admin`, but
the show pages now follow the same general shape: overview fields first, then
tabbed related collections or related-record panels underneath.

## Quick start

Run the backend first on port `5656`, then start the frontend:

```bash
npm install
npm run dev
```

End-to-end browser coverage:

```bash
npm run test:e2e
```

The Playwright config uses system Chromium and starts the frontend on port
`4173` for tests.

Default backend targets:

- API root: `http://127.0.0.1:5656/api`
- Admin schema: `http://127.0.0.1:5656/ui/admin/admin.yaml`

Override them with:

- `VITE_API_ROOT`
- `VITE_ADMIN_YAML_URL`

## Notes

The current Vite config includes a small browser shim for `fs/promises`.
That is only there because `safrs-jsonapi-client` currently bundles a Node-only
file loader in the same module graph as the browser-facing schema helpers.
