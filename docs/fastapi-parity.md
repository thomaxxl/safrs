# FastAPI attribute-parsing parity

SAFRS model behavior is the reference contract for every framework adapter.
Both Flask and FastAPI pass incoming resource attributes through
`SAFRSBase._s_parse_attr_value`. This includes:

- SQLAlchemy column coercion, including strict `Date`, `DateTime`, and `Time`
  parsing;
- `jsonapi_attr` parser and validator hooks;
- read-only `jsonapi_attr` enforcement; and
- ignoring attributes that are not exposed by `_s_jsonapi_attrs`.

Malformed values raise `ValidationError`, produce a `400` JSON:API error
response, and are not persisted. Framework adapters must not substitute a
default value or restore the original unparsed input.

## Compatibility change

The former FastAPI-specific temporal parser had three differences from SAFRS:

- it accepted `T` as the `DateTime` date/time separator while SAFRS accepts a
  space;
- it converted `Date` strings to `datetime.date` before SQLAlchemy assignment,
  while SAFRS returns a midnight `datetime.datetime` for the assignment; and
- after any parsing failure, it restored the original input and allowed the
  request to continue.

Those differences have been removed. FastAPI now follows SAFRS exactly. In
particular, a value such as `2024-02-29T01:02:03` is rejected with `400`; use
`2024-02-29 01:02:03`.

## Remaining adapter drift

Attribute-value parsing has no intentional adapter drift. Structural request
validation still differs: FastAPI/Pydantic reports a structurally invalid
request body as `422`, while Flask/SAFRS generally reports malformed JSON:API
documents as `400`. This happens before model attribute parsing.
