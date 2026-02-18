# Spec Parity Rules

## Level 1 (must match)
- Operations: FastAPI must expose every Flask operation (path + method).
- Core status codes: FastAPI must include every status code documented by Flask per shared operation.
- JSON:API request bodies: when Flask documents a request body, FastAPI must document it.
- Error media type: JSON:API errors are documented under `application/vnd.api+json`.

## Level 2 (should match)
- JSON:API query parameters:
  - `include`
  - `fields[TYPE]`
  - `page[offset]`, `page[limit]`
  - `sort`
  - `filter`, `filter[<attr>]`
- Collection vs instance response schema shapes should match endpoint semantics.
- Relationship GET should document resource documents; relationship mutations should document linkage payloads.

## Level 3 (nice to have)
- Tag descriptions and route descriptions closely mirror Flask SAFRS docs.
- Rich examples for request/response payloads.
- RPC endpoint docs include parameter and result structures.
