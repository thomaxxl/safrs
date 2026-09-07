# Synchronous performance: measurements and next steps

The performance suite exercises real Flask and FastAPI requests against SQLite,
including SQL execution, ORM loading, authorization and JSON response rendering.
It found and fixes an eager-loading bug in `safrs/jsonapi_filters.py:create_query`:
SQLAlchemy stores `lazy` on `RelationshipProperty`, not `InstrumentedAttribute`.
The previous lookup silently skipped the `OPTIMIZED_LOADING` loader options on
real mapped models. Existing mocks supplied `.lazy` on the attribute and missed
the problem.

The fix reads the mapper relationship metadata and retains the existing joined
loader strategy, supported loader modes, include limits and authorization paths.
Dynamic, noload and raise relationships still do not receive eager-load options.
Async execution and concurrency changes are outside this work.

## Run the telemetry tests

From the package repository, using an environment with its test dependencies:

```sh
python -m pytest tests/performance --perf-report=/tmp/safrs-performance.json
```

There are no extra benchmark dependencies. The default is one unmeasured warmup
and five measured requests per workload. A larger diagnostic run is:

```sh
python -m pytest tests/performance --perf-samples=30 \
  --perf-report=/tmp/safrs-performance.json \
  --junitxml=/tmp/safrs-performance.xml -o junit_family=legacy
```

Use a separate invocation for Python allocation measurements:

```sh
python -m pytest tests/performance --perf-memory --perf-samples=3 \
  --perf-report=/tmp/safrs-performance-memory.json
```

Run serially, without pytest-xdist, coverage, a profiler or unrelated load when
comparing latency. Run coverage separately when validating the collector. In the
example workspace, the equivalent container command after merging is:

```sh
./run.sh test safrs/tests/performance --perf-report=/app/safrs-performance.json
```

That workspace command enables coverage, so its timings are diagnostic only.
The workspace watcher (`/tmp/run_safrs_tests`) runs the default integration suite;
it does not automatically discover package tests under `safrs/tests/performance`.

The terminal table and optional JSON report contain p50/p95 request latency,
process CPU time, cursor execution time, SQL counts, COUNT query counts,
repeated SQL shapes, ORM instance loads and response bytes. Raw samples and
environment metadata are retained, including the imported package path, Git
revision and a source-content hash that distinguishes uncommitted code. JUnit
gets a `performance` test property. Assertions check response contents, query
ceilings and loaded-object counts; there are no wall-clock pass/fail thresholds.
Failed assertions are marked in the JSON report and its process exit status.

Each request starts with an empty ORM session. Database seeding, route exposure,
warmup, session reset and response JSON parsing are outside the measured window.
FastAPI uses a persistent test-client context and avoids redirects. SQLite uses
an in-memory database; framework and database caches remain warm. This is not
a cold-disk, remote-database, throughput or concurrency benchmark.

Cursor timing excludes fetching rows and ORM hydration, so it cannot be treated
as total database time. Process CPU includes all threads. Memory mode reports
peak traced Python allocations, not RSS or native database allocations, and
substantially distorts latency. Event listeners add some overhead even without
memory tracing. SQL parameters and statements are not included in reports.
With five samples, nearest-rank p95 is simply the maximum sample; use larger
runs and repeated experiments before drawing timing conclusions.

## Findings

Measurements below used 80 parents, 12 children and 8 labels per parent, with a
2 KiB parent description, SQLAlchemy 2.0.48 and SQLite 3.45.1 on Python 3.12.3.
The local before/after Flask runs used three/five samples respectively; these
are illustrative observations, not stable latency targets. Container validation
also confirmed the query ceilings on both adapters.

| Request | SQL before | SQL after | Local p50 before → after |
| --- | ---: | ---: | ---: |
| 25 parents, no includes | 2 | 2 | 8.76 → 8.77 ms |
| 25 parents, `include=children` | 27 | 2 | 81.21 → 73.72 ms |
| 25 parents, `include=children.parent` | 27 | 2 | 89.69 → 79.39 ms |
| 25 parents, `include=children,labels` | 52 | 2 | 122.38 → 123.70 ms |

The sibling-collection result matters: fewer queries do not always mean less
work. Join multiplication can offset saved round trips on a local database.

### 1. Make collection loader strategy configurable

`create_query` currently uses joined loading for all supported relationships,
including mappings configured with `lazy="selectin"`. With sibling collections,
the fixture's join produces a calculated 25 × 12 × 8 = 2,400 result rows for
525 distinct ORM objects. A select-in strategy retrieves those objects across
four queries including the count, without the cross product.

`test_loader_comparison` switches to select-in loading **only in the test** and
compares the complete response with production joined loading. The local
25-parent sibling experiment measured p50 123.70 ms for joined loading and
109.31 ms for select-in loading. In a separate allocation run, median peak traced
memory fell from approximately 6.18 MB to 1.48 MB. Container timing results were
mixed, so this establishes a promising memory tradeoff rather than a universal
latency win.

Consider an explicit strategy setting, retaining joined loading for suitable
to-one relationships and evaluating select-in loading for to-many relationships.
Check nested paths, composite keys, target authorization and supported database
dialects before changing defaults. In particular, tuple-IN support limits some
composite-key/database combinations. See SQLAlchemy's
[relationship loading guidance](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#what-kind-of-loading-to-use).

### 2. Batch Flask relationship-list filtering

`jsonapi_formatting.jsonapi_filter_list` builds and executes a primary-key filter
for every child in an already-loaded relationship. Returning five children from
a twelve-child collection costs **14 SQL statements and 13 ORM loads** on Flask.
The corresponding FastAPI list relationship uses two statements, but still loads
all twelve children before slicing. Dynamic relationship pagination uses three
statements and loads only the parent plus the five returned children on both.

Move list membership filtering into a set-based query, ideally before loading
the relationship. Preserve composite keys, custom filters, query scopes and
per-row permissions; simply trusting an already-loaded list would change access
decisions. Add cardinality-scaling tests when implementing this so query count
stays bounded as relationship size grows. The current suite retains the measured
ceiling as a baseline, allowing future reductions.

### 3. Remove redundant dynamic-relationship counts

`SAFRSBase._s_related_collection_data` executes an unrestricted count, a second
count after applying the limit, and then a fetch for each included dynamic
relationship. For 25 parents that is **77 statements, including 51 COUNTs**, on
both adapters. The second count is used only for the truncation warning.

Investigate calculating that warning from the already-returned items or the
existing count and limit, preserving its threshold behavior and scoped totals.
Then consider batching dynamic includes. Keep ordinary relationship pagination
available: a single dynamic relationship page already uses three statements.

### 4. Reduce repeated serialization metadata work

A cProfile run of five 25-parent sibling-include requests after the fix recorded
2,625 resource serializations and 5,250 calls to the class-level
`_s_jsonapi_attrs` expression. Attribute extraction consumed about 1.27 s of
2.32 s total profiled time; nested cumulative times must not be added together.
`get_config` was called 21,330 times. These are profiling observations, not
uninstrumented request latencies.

Start by reusing attribute metadata within a single serialization, caching
immutable mapper structure independently of permissions, and parsing include
paths/sparse fieldsets once per request. Preserve custom extension semantics.
Do **not** globally cache permission-filtered fields or per-row decisions:
`base.py` explicitly avoids that cache because callers can have different field
visibility. Keep row-dependent checks at their existing scope. The concurrent
authorization changes should be assessed before implementing this optimization.

Sparse fields already reduce the 25-parent Flask payload from 60,323 to 8,770
bytes, but still issue the same SQL and hydrate the same 25 objects. A future
column-projection optimization must account for computed attributes and policy
hooks that access omitted columns, or it could introduce deferred-column N+1s.

### 5. Benchmark pagination against production-sized data

Both adapters currently use a count and an offset/limit query for ordinary
collections. The telemetry covers filtered totals and later offsets, but this
small SQLite fixture cannot establish the cost of large counts, sorts or deep
offsets on PostgreSQL/MySQL. Inspect actual query plans and application indexes,
then benchmark large datasets. Optional cursor pagination or optional totals
would be API features requiring explicit contract decisions. Keep current scoped
counts and links correct while optimizing them.

Similarly, `materialize_for_authorization` can turn a query into an in-memory
policy scan before pagination when a model needs row-dependent checks. Prefer
expressing eligible application policies through the existing query-scope hooks
where possible; never skip authorization to retain database pagination.

SQLAlchemy's [performance FAQ](https://docs.sqlalchemy.org/en/20/faq/performance.html)
explains the distinction between cursor execution, result fetching and ORM work
that these measurements are designed to expose.
