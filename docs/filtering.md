# SAFRS Filtering

This page documents the current filtering behavior in SAFRS for collection endpoints.

## 1) Attribute filters (`filter[<attr>]`)

Use query parameters like:

- `GET /Users/?filter[name]=John`
- `GET /Users/?filter[name]=John,Jane`

Behavior:

- `filter[<attr>]` is parsed as a CSV list and translated to SQL `IN (...)`.
- Multiple `filter[<attr>]` parameters are combined with `AND`.
- `id` is supported as a special case.
- Unknown attributes are rejected.

This mode is simple and fast for exact-value matching.

## 2) JSON filter payload (`filter=...`)

Use `filter` with a JSON value when you need operators or boolean groups.

### Clause format

Each clause object uses:

- `name`: attribute name (or `id`)
- `op`: operator
- `val`: value

Example:

```text
filter={"name":"name","op":"eq","val":"Author 0"}
```

### Supported operators

- `eq`, `ne`
- `lt`, `le`, `gt`, `ge`
- `like`, `ilike`, `match`, `notilike`
- `in`, `notin`
- `is`, `is_`, `is_not`

Notes:

- `like` / `ilike` / `match` / `notilike` expect string values.
- `in` / `notin` expect array values.

## 3) Grouped boolean filtering (recommended)

Grouped mode is enabled when the JSON payload contains `and`, `or`, or `not`.
This is the preferred format for predictable boolean logic.

Examples:

```text
filter={"and":[{"name":"age","op":"ge","val":18},{"name":"age","op":"lt","val":65}]}
```

```text
filter={"or":[{"name":"name","op":"eq","val":"Alice"},{"name":"name","op":"eq","val":"Bob"}]}
```

```text
filter={"and":[{"or":[{"name":"status","op":"eq","val":"active"},{"name":"status","op":"eq","val":"pending"}]},{"not":{"name":"archived","op":"eq","val":true}}]}
```

Rules:

- Exactly one group key per object: `and` or `or` or `not`.
- `and` / `or` require a non-empty array.
- `not` requires a single object.

## 4) Legacy JSON mode (compatibility)

If `filter` JSON does not use group keys, SAFRS keeps legacy behavior:

- A single clause object works.
- A list of clauses is treated as `OR` between clauses.

For backward compatibility, legacy `in` / `notin` handling is preserved exactly as before.

## 5) Validation behavior

Invalid filters raise a JSON:API validation error (for example):

- invalid JSON in `filter`
- unknown attribute
- unknown operator
- malformed group structure

Current limitation:

- Relationship-path filtering with dotted names (for example `author.name`) is not supported.

## 6) Custom filtering hooks

You can customize filtering in three ways:

1. Implement a class method named `filter` to receive raw `filter=` input.
2. Override `SAFRSBase._s_filter(cls, *args, **kwargs)`.
3. Provide a custom `jsonapi_filter` strategy for the model/API.

Example override:

```python
class User(SAFRSBase, db.Model):
    id = db.Column(db.String, primary_key=True)
    username = db.Column(db.String(32))

    @classmethod
    def _s_filter(cls, *args, **kwargs):
        value = args[0] if args else ""
        return cls.query.filter_by(username=value)
```

## 7) URL encoding tip

Because grouped filters are JSON strings, URL-encode the value when calling from curl or clients.
For curl, prefer `--get --data-urlencode` to avoid malformed query strings.
