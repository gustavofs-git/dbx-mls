# Phase 2: Bronze Ingestion Pipeline - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Bronze ingestion pipeline: `src/riot_client.py` (dual-bucket rate limiter + API
client), `src/config.py` (platform routing + job params), 6 ingestion modules writing to
`lol_analytics.bronze.*` via MERGE dedup, `bronze.ingestion_log`, unit tests, and the
`resources/jobs/ingestion_job.yml` DAB job definition.

This phase delivers working Bronze tables populated with real KR Challenger data. No Silver
parsing, no Gold aggregations — those are Phases 3 and 4.

</domain>

<decisions>
## Implementation Decisions

### API Fetch Execution Model

- **D-01:** All API calls execute in plain Python `for` loops on the **Spark driver** — no
  Spark-distributed fetch, no `mapPartitions`, no worker-side HTTP calls. The dual-bucket
  rate limiter singleton is shared naturally within the driver process. The sequential
  dependency chain (league entries → match IDs → match raw) aligns with this model.
  Spark is used for Delta writes only.

### Partial Failure Recovery

- **D-02:** **Restart-clean, rely on MERGE deduplication.** If the job dies mid-run, the
  next run starts from the beginning of the chain. MERGE idempotency (dedup on primary
  keys) and the anti-join pre-check (`bronze.match_ids` vs `bronze.match_raw`) mean
  re-running wastes zero API calls on already-ingested matches. No checkpoint file, no
  resume-from-offset logic. This is the correct design given the 4-hour timeout budget
  and the existing MERGE pattern.

### LinkedIn Phase 2 Deliverable

- **D-03:** Same full-story format as Phase 1 BR article — technical deep-dive with real
  code snippets, covering the complete Phase 2 scope (rate limiter, MERGE dedup, 6 Bronze
  tables, DAB task DAG) as one coherent narrative. Short post + detailed article pair.
- **D-04:** **The article MUST be written AFTER human acceptance testing (UAT) passes**,
  not as part of Plan 02-05 execution. Real pipeline results (actual row counts from
  `SELECT COUNT(*) FROM lol_analytics.bronze.match_raw`, verified MERGE idempotency run)
  should be incorporated into the article before it is committed. The article is a
  post-UAT deliverable, not a pre-testing artifact.
- **D-05:** Article will be generated in English first, then the LPH agent humanizes and
  translates to Brazilian Portuguese — same workflow as Phase 1.

### ingestion_log Schema

- **D-06:** Use the 7-field schema exactly as defined in ROADMAP.md:
  `(batch_id, run_start, run_end, requests_made, count_429, new_matches_ingested, status)`.
  No per-endpoint breakdowns, no error_message column. Simple, sufficient, and doesn't
  complicate the implementation.

### Claude's Discretion

- Exact `ingestion_log` Delta table properties (partitioning, clustering)
- Python package structure within `src/` (whether `__init__.py` files are needed for pytest
  import resolution — follow whatever pattern makes `pytest tests/unit/` work locally)
- Logging verbosity levels and exact log message formats in `src/common/logger.py`
- Order of SQL columns in CREATE TABLE / MERGE statements (schema consistency over aesthetics)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` §Bronze Ingestion (BRZ-01 through BRZ-10), §Testing (TEST-02, TEST-04)
- `.planning/ROADMAP.md` §Phase 2 — Five detailed plan definitions with exact deliverables,
  file paths, class/method names, table schemas, acceptance criteria, and task DAG

### Project Architecture
- `.planning/PROJECT.md` — Core value, constraints (rate limits, UC-only, no DBFS, parameterization),
  key decisions table, out-of-scope items
- `.planning/STATE.md` §Accumulated Context — Phase 1 constraints that apply here:
  `data_security_mode: SINGLE_USER`, `source: GIT`, `DATABRICKS_HOST` via env var

### Prior Phase Context
- `.planning/phases/01-infrastructure-governance-ci-cd-foundation/01-CONTEXT.md` — Cluster
  config decisions (Standard_F4s_v2, autotermination, SINGLE_USER), LinkedIn article format
  decisions (D-11 through D-14), established patterns

### Existing Infrastructure (read before implementing)
- `databricks.yml` — Bundle root; `resources/jobs/ingestion_job.yml` will replace the
  current placeholder `jobs: {}`
- `resources/schemas.yml` — UC schema declarations already deployed
- `.github/workflows/ci.yml` — CI already runs `pytest tests/unit/ --cov=src`; Phase 2
  unit tests drop in without CI changes
- `requirements-dev.txt` — `pytest-mock`, `pyspark==3.5.3`, `delta-spark==3.3.2`, `chispa`
  already present

No external API specs — Riot API routing and endpoint details are fully captured in ROADMAP.md
plan definitions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `notebooks/smoke_test.py` — Reference for how to use `dbutils.secrets.get()` and Spark
  SQL in a DAB notebook task (import pattern, session access)
- `requirements-dev.txt` — Test stack already wired: `pytest-mock` for HTTP mocking,
  `pyspark` local mode, `chispa` for DataFrame assertions
- `pytest.ini` — Pytest config already present; extend rather than replace

### Established Patterns
- Delta table writes use UC three-part names (`lol_analytics.bronze.*`) — no DBFS, no
  `hive_metastore` — established by `resources/schemas.yml`
- DAB job clusters: `Standard_F4s_v2`, `data_security_mode: SINGLE_USER`,
  `autotermination_minutes: 0` (job cluster terminates with job)
- DAB task notebooks use `source: GIT` (not `WORKSPACE`) — SP file access restriction
  in UC workspace; GIT pulls from public GitHub at runtime
- `DATABRICKS_HOST` set via env var, NOT in `databricks.yml` (CLI v0.295.0 rejects variable
  interpolation for auth fields)

### Integration Points
- `resources/jobs/ingestion_job.yml` replaces the current `jobs: {}` placeholder — this
  is where the full DAB job definition (5 tasks, job-level params, timeout) goes
- `src/` is fully empty — all new modules land here. No conflicts with existing code.
- `tests/unit/` has only `test_placeholder.py` — add `test_riot_client.py` and
  `test_config.py` alongside it
- CI (`ci.yml`) already runs `pytest tests/unit/ --cov=src` — no CI changes needed for
  Phase 2 tests to run in CI

</code_context>

<specifics>
## Specific Ideas

- **LinkedIn article timing:** User explicitly wants the article written AFTER UAT validates
  real data in Bronze tables. The article should reference actual query results (e.g.,
  `SELECT COUNT(*) FROM lol_analytics.bronze.match_raw` returning real numbers). This means
  Plan 02-05 should NOT commit the article — the article is committed after UAT sign-off.
- **Format reference:** `docs/posts/br/phase-1br-article.md` is the canonical format
  reference for Phase 2 article. Same structure: "O que foi entregue" → technical sections
  with code blocks → "O Que Vem na Fase N."
- **BR post reference:** `docs/posts/br/phase-1br-post.md` is the format reference for the
  short LinkedIn post — personal/authentic tone, ~5 lines, hashtags at end.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 2 scope.

</deferred>

---

*Phase: 02-bronze-ingestion-pipeline*
*Context gathered: 2026-04-13*
