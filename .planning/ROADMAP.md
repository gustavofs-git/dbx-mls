# Roadmap: dbx-mls — Databricks Modern Lakehouse (League of Legends)

## Overview

This roadmap delivers a production-grade Azure Databricks Medallion Architecture pipeline
ingesting League of Legends data from the Riot Games API. The journey moves from infrastructure
and CI/CD foundations (Phase 1) through Bronze raw ingestion (Phase 2), Silver schema-enforced
transformations (Phase 3), Gold analytics aggregations (Phase 4), and finally portfolio
presentation with MCP showcase and the full LinkedIn content series (Phase 5). Every phase
produces a verified, deployable artifact — nothing is speculative until it runs.

## Phases

- [ ] **Phase 1: Infrastructure, Governance & CI/CD Foundation** - Prove the full deploy path before writing a single line of pipeline code
- [ ] **Phase 2: Bronze Ingestion Pipeline** - Ingest raw Riot API JSON to Unity Catalog Delta tables with a production-grade rate limiter
- [ ] **Phase 3: Silver Transformation Layer** - Parse, flatten, and schema-enforce all Bronze JSON into typed Delta tables with full test coverage
- [ ] **Phase 4: Gold Analytics Layer** - Aggregate Silver into queryable champion, pick/ban, and tier distribution analytics tables
- [ ] **Phase 5: Portfolio Polish, MCP Showcase & LinkedIn Posts** - Ship the README, Makefile, MCP integration, and the full LinkedIn content series

## Phase Details

---

### Phase 1: Infrastructure, Governance & CI/CD Foundation

**Goal**: Prove that GitHub Actions can authenticate as a Service Principal via OIDC, deploy a
trivial DABs smoke-test job, and own the Unity Catalog schemas — establishing the ownership and
auth baseline that every subsequent phase depends on.

**Depends on**: Nothing (first phase)

**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07,
CICD-01, CICD-02, CICD-03, CICD-04, CICD-05, CICD-06

**Success Criteria** (what must be TRUE):
  1. `databricks bundle validate` passes locally and in CI with zero errors or warnings
  2. A push to `main` triggers CI (`validate → pytest`) and deploys the bundle to the `dev` target without any PAT token — only OIDC
  3. `SHOW GRANTS ON SCHEMA lol_analytics.bronze` confirms the SP (not a human user) is schema owner for `bronze`, `silver`, and `gold`
  4. A smoke-test DAB job (trivial notebook that prints "hello world") runs end-to-end from CI trigger to Databricks job completion in the `dev` workspace
  5. The Riot API key is retrievable inside a notebook via `dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")` and redacted in all logs

**Plans**: 4 plans

Plans:
- [x] 01-01: Repo scaffold, DABs `databricks.yml`, and workspace prerequisites
- [x] 01-02: OIDC federation and GitHub Actions CI/CD workflows
- [x] 01-03: Unity Catalog schemas, SP ownership grants, and Databricks Secrets
- [ ] 01-04: Smoke-test job, end-to-end deploy validation, and `.gitignore` hardening

**UI hint**: no

---

#### Plan 01-01: Repo Scaffold, DABs `databricks.yml`, and Workspace Prerequisites

**Complexity**: Medium

**Requirements covered**: INFRA-01, INFRA-04, INFRA-07

**Depends on**: Nothing

**Delivers**:
- Full repo directory tree committed: `databricks.yml`, `resources/`, `src/`, `schemas/`,
  `notebooks/`, `tests/`, `.github/workflows/`, `docs/posts/`, `Makefile`,
  `requirements.txt`, `requirements-dev.txt`
- `databricks.yml` with `bundle.name: dbx-mls`, `bundle.databricks_cli_version: ">=0.250.0"`,
  `dev` target (`mode: development`, `default: true`) and `prod` target (`mode: production`,
  explicit `root_path: /Workspace/Shared/.bundle/dbx-mls/prod`, `run_as` SP reference)
- `resources/` split into `schemas.yml`, `clusters.yml`, `jobs/ingestion_job.yml`,
  `jobs/transformation_job.yml` — all referenced via `include:` in `databricks.yml`
- `resources/clusters.yml` defines a single `job_cluster` with DBR 16.4 LTS
  (`spark_version: 15.4.x-scala2.12` placeholder until confirmed), `node_type_id`,
  `spark.databricks.cluster.profile: singleUser`
- `requirements.txt`: `requests>=2.32.0`, `tenacity>=9.0.0`, `databricks-sdk>=0.102.0`
- `requirements-dev.txt`: inherits `requirements.txt` plus `pyspark==3.5.2`,
  `delta-spark==3.3.2`, `pytest>=8.3.0`, `chispa>=0.9.4`, `pytest-cov>=6.0.0`,
  `pytest-mock>=3.14.0`, `azure-identity>=1.19.0`
- `.gitignore` excludes: `.env`, `*.pyc`, `__pycache__/`, `.databricks/`, `*.egg-info`,
  `dist/`, `.venv/`, `*.token`, `secrets.yml`
- Azure Databricks workspace exists (manual prerequisite, documented in `docs/setup.md`)
- Databricks CLI 0.295+ installed and authenticated locally via `databricks auth login`

**Key constraint**: Do NOT run `databricks bundle deploy` locally against any target yet —
schema ownership is set on first deploy and cannot be cleanly transferred.

**Acceptance**: `databricks bundle validate` exits 0 locally with no errors.

---

#### Plan 01-02: OIDC Federation and GitHub Actions CI/CD Workflows

**Complexity**: Complex

**Requirements covered**: CICD-01, CICD-02, CICD-03, CICD-04, CICD-05, CICD-06

**Depends on**: Plan 01-01 (repo structure must exist for workflows to reference)

**Delivers**:
- Service Principal created at Databricks account level (numeric SP ID noted separately
  from the UUID `DATABRICKS_CLIENT_ID`)
- Federation policy created for `dev` target:
  `subject: "repo:<org>/dbx-mls:ref:refs/heads/main"` (branch-scoped, no environment)
- Federation policy created for `prod` target:
  `subject: "repo:<org>/dbx-mls:environment:prod"` (environment-scoped — exact match required)
- GitHub repository variables (not secrets): `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`
- GitHub Environment `prod` created with manual approval protection rule
- `.github/workflows/ci.yml`: triggers on `push` to any branch; steps:
  `actions/checkout@v4` → `actions/setup-python@v5` (python 3.12) →
  `pip install -r requirements-dev.txt` → `databricks bundle validate` →
  `pytest tests/unit/ --cov=src --cov-report=xml`
  Permissions: `id-token: write`, `contents: read`
  Auth env vars: `DATABRICKS_AUTH_TYPE: github-oidc`, `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`
  CLI: `databricks/setup-cli@main` (pinned to specific release in `cd-prod.yml`)
- `.github/workflows/cd-dev.yml`: triggers on push to `main`; steps:
  `databricks bundle deploy --target dev`
  Uses same OIDC vars as CI; no `environment:` key (branch-scoped federation policy)
- `.github/workflows/cd-prod.yml`: triggers on tag push `v*`; job uses `environment: prod`
  (must exactly match federation policy subject); `concurrency: { group: prod-deploy,
  cancel-in-progress: false }`; CLI pinned to specific version
  (`databricks/setup-cli@v0.295.0` or equivalent)
  Steps: manual approval gate (via GitHub Environment) → `databricks bundle deploy --target prod`
- `checkout@v4` uses `ref: ${{ github.ref }}` to avoid detached HEAD on tag events

**Critical pitfall**: The `environment:` key in `cd-prod.yml` job block must exactly match
`environment:prod` in the federation policy subject claim (case-sensitive, no spaces).

**Acceptance**: Push to `main` triggers `ci.yml` (validate + pytest) and `cd-dev.yml` (deploy)
both succeed with green checkmarks in GitHub Actions, zero PAT tokens in secrets.

---

#### Plan 01-03: Unity Catalog Schemas, SP Ownership Grants, and Databricks Secrets

**Complexity**: Medium

**Requirements covered**: INFRA-02, INFRA-03, INFRA-05

**Depends on**: Plan 01-02 (SP must exist before grants can be written)

**Delivers**:
- `resources/schemas.yml` declares `lol_analytics` catalog (or references existing one if
  workspace admin pre-created it) and three schemas: `bronze`, `silver`, `gold` — owned by
  the CI SP from day one
- Grant script documented in `docs/setup.md` and executed once by workspace admin:
  ```sql
  GRANT USE CATALOG ON CATALOG lol_analytics TO `<sp-app-id>`;
  GRANT CREATE SCHEMA ON CATALOG lol_analytics TO `<sp-app-id>`;
  GRANT USE SCHEMA ON SCHEMA lol_analytics.bronze TO `<sp-app-id>`;
  GRANT CREATE TABLE ON SCHEMA lol_analytics.bronze TO `<sp-app-id>`;
  GRANT MODIFY ON SCHEMA lol_analytics.bronze TO `<sp-app-id>`;
  -- repeat for silver, gold
  ```
- SP added to Databricks workspace with "Can Manage" or appropriate workspace-level role
- Databricks Secret Scope `lol-pipeline` created; Riot API key stored as `riot-api-key`
- Secret ACL grants SP `CAN_READ` on the `lol-pipeline` scope
- `docs/setup.md` documents: workspace provisioning prerequisites, how to obtain/rotate the
  Riot Dev API key (24h expiry), permanent personal API key process

**Verification**: Run `SHOW GRANTS ON SCHEMA lol_analytics.bronze` — must show SP as owner,
NOT any human user email.

**Acceptance**: `databricks secrets list-secrets lol-pipeline` shows `riot-api-key` (redacted).

---

#### Plan 01-04: Smoke-Test Job, End-to-End Deploy Validation, and `.gitignore` Hardening

**Complexity**: Simple

**Requirements covered**: INFRA-06

**Depends on**: Plans 01-01, 01-02, 01-03

**Delivers**:
- `notebooks/smoke_test.py` — trivial notebook that:
  1. Reads `dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")` (redacted in logs)
  2. Runs `spark.sql("SHOW SCHEMAS IN lol_analytics").show()` to confirm UC access
  3. Creates a test row in `lol_analytics.bronze.smoke_test` temp table, reads it back, drops it
  4. Prints "SMOKE TEST PASSED"
- `resources/jobs/smoke_test_job.yml` DAB job definition referencing the notebook
- CI `cd-dev.yml` extended to run `databricks bundle run smoke_test_job --target dev`
  post-deploy and assert exit code 0
- `.gitignore` verified: `git status --short` shows zero untracked credential files
- `Makefile` initial targets: `make validate`, `make test`, `make smoke` (for local use)

**Acceptance**: A fresh push to `main` results in: CI green → dev deploy green →
smoke test job completes successfully in the dev workspace → `SMOKE TEST PASSED` visible
in job run logs.

**LinkedIn deliverable**: Phase 1 article + short post committed to
`docs/posts/phase-1-article.md` and `docs/posts/phase-1-post.md`

---

### Phase 2: Bronze Ingestion Pipeline

**Goal**: Ingest raw Riot Games API responses for League entries, match IDs, match details,
match timelines, summoner profiles, and account details into Unity Catalog Delta Bronze tables
using a production-grade dual-bucket rate limiter with full deduplication.

**Depends on**: Phase 1 (SP owns schemas, CI/CD proven, secrets accessible)

**Requirements**: BRZ-01, BRZ-02, BRZ-03, BRZ-04, BRZ-05, BRZ-06, BRZ-07, BRZ-08, BRZ-09,
BRZ-10, TEST-02, TEST-04

**Success Criteria** (what must be TRUE):
  1. A DAB job run with parameters `region=KR, tier=CHALLENGER` completes end-to-end and
     populates `lol_analytics.bronze.league_entries`, `bronze.match_ids`, and
     `bronze.match_raw` with real KR Challenger data — verifiable via
     `SELECT COUNT(*) FROM lol_analytics.bronze.match_raw`
  2. Re-running the same job does not create duplicate rows in `bronze.match_raw` — the
     MERGE deduplication on `match_id` is verified by row count being identical after second run
  3. A job run with `region=NA1, tier=DIAMOND` requires zero code changes — only the DAB
     job parameters change
  4. `pytest tests/unit/test_riot_client.py` passes locally (mocked HTTP, no live API key)
     and passes in CI with the rate limiter logic, 429 handling, and routing dict all covered
  5. `bronze.match_timeline_raw` is populated by a separate DAB task that can be skipped
     or re-run independently without affecting `bronze.match_raw`

**Plans**: 5 plans

Plans:
- [ ] 02-01: `src/riot_client.py` — dual-bucket rate limiter and API client
- [ ] 02-02: `src/config.py` — platform-to-routing mapping and job parameter handling
- [ ] 02-03: Bronze ingestion — League entries, match IDs, and match raw (core chain)
- [ ] 02-04: Bronze ingestion — Match timeline, summoner, and account (enrichment tasks)
- [ ] 02-05: DAB ingestion job definition, unit tests, and CI integration

**UI hint**: no

---

#### Plan 02-01: `src/riot_client.py` — Dual-Bucket Rate Limiter and API Client

**Complexity**: Complex

**Requirements covered**: BRZ-01

**Depends on**: Phase 1 complete

**Delivers**:
- `src/riot_client.py` implementing:
  - `RiotRateLimiter` class: thread-safe dual-bucket token bucket enforcing both
    20 req/sec AND 100 req/2min buckets simultaneously; refill logic uses `time.monotonic()`
  - `call_riot_api(url, headers, limiter, params)` function:
    - Calls `limiter.acquire()` before each request
    - On 429: reads `X-Rate-Limit-Type` header; if `application` or `method`, sleeps
      exactly `Retry-After` seconds then retries; if `service`, exponential backoff
      with jitter
    - Parses and logs `X-App-Rate-Limit-Count` header on every response (structured log)
    - Raises typed `RiotApiError` on 4xx/5xx (not bare `requests.exceptions.HTTPError`)
    - Timeout: 10 seconds per request
  - Uses synchronous `requests` — no `asyncio`, no `httpx`
- `src/common/logger.py` — structured logging helper (JSON-formatted to stdout)
- `src/common/exceptions.py` — `RiotApiError`, `RateLimitError`

**Key constraints**:
- Do NOT use `time.sleep(0.05)` as the primary throttle mechanism
- `KR` must map to `asia` regional host, never `kr.api.riotgames.com` for Match-V5
- The rate limiter must be a shared singleton per Spark driver process (not per-call instance)

**Acceptance**: `python -m pytest tests/unit/test_riot_client.py -v` passes with mocked
HTTP responses covering: normal call, 429 with `Retry-After`, service-level 429, and 404.

---

#### Plan 02-02: `src/config.py` — Platform Routing Map and Job Parameter Handling

**Complexity**: Simple

**Requirements covered**: BRZ-02, BRZ-03

**Depends on**: Plan 02-01 (imports `logger`)

**Delivers**:
- `src/config.py` containing:
  - `PLATFORM_TO_REGION: dict[str, str]` — complete 17-entry mapping:
    KR/JP1 → `asia`, NA1/BR1/LA1/LA2 → `americas`, EUW1/EUN1/TR1/RU/ME1 → `europe`,
    OC1/PH2/SG2/TH2/TW2/VN2 → `sea`
  - `RANKED_QUEUE = "RANKED_SOLO_5x5"` — the only queue supported in v1
  - `get_platform_host(platform: str) -> str` — returns `{platform}.api.riotgames.com`
  - `get_region_host(platform: str) -> str` — looks up `PLATFORM_TO_REGION`, returns
    `{region}.api.riotgames.com`; raises `ConfigError` for unknown platforms
  - `get_job_params(dbutils) -> dict` — reads `region` and `tier` from Databricks job
    parameters via `dbutils.widgets.get()`; validates against known platforms;
    defaults `region=KR`, `tier=CHALLENGER`
  - `DEFAULT_MATCH_COUNT = 20` — max match IDs fetched per PUUID
  - `JOB_TIMEOUT_SECONDS = 14400` — 4-hour timeout documented as constant for DAB config
- `PLATFORM_TO_REGION` is the single source of truth — never hardcoded elsewhere

**Acceptance**: `python -m pytest tests/unit/test_config.py -v` covers routing lookups,
unknown platform error, and widget parameter parsing (mocked `dbutils`).

---

#### Plan 02-03: Bronze Ingestion — League Entries, Match IDs, and Match Raw (Core Chain)

**Complexity**: Complex

**Requirements covered**: BRZ-04, BRZ-05, BRZ-06, BRZ-10

**Depends on**: Plans 02-01, 02-02 (requires rate limiter and config)

**Internal dependency chain**:
- Step A: League-Exp-V4 fetch → `bronze.league_entries` (produces PUUID list)
- Step B: Match-V5 by-puuid → `bronze.match_ids` (requires PUUIDs from Step A)
- Step C: Match-V5 detail → `bronze.match_raw` (requires new match IDs from Step B)
- Steps A/B/C must execute in series — B cannot start until A has PUUIDs,
  C cannot start until B has match IDs and dedup is complete

**Delivers**:
- `src/ingestion/bronze_league_entries.py`:
  - Paginates League-Exp-V4 with `?page=n` until empty list returned (1-indexed stop condition)
  - Handles 10,000-entry cap gracefully (not treated as error)
  - MERGE writes to `lol_analytics.bronze.league_entries` on `(puuid, _region, _tier)` —
    inserts new rows only (`WHEN NOT MATCHED THEN INSERT *`)
  - Metadata columns: `_ingested_at`, `_source_url` (URL without API key), `_region`,
    `_tier`, `_page`, `_batch_id` (UUID generated once per job run)
  - Partitioned by `(_region, tier)` as per FEATURES.md schema design
- `src/ingestion/bronze_match_ids.py`:
  - Reads PUUIDs from `bronze.league_entries` (current `_region`/`_tier` filter)
  - For each PUUID: fetches `/by-puuid/{puuid}/ids?queue=420&start=0&count=20`
  - MERGE writes to `lol_analytics.bronze.match_ids` on `(puuid, match_id)`
  - Deduplication: new `(puuid, match_id)` pairs only — no re-fetching already seen pairs
- `src/ingestion/bronze_match_raw.py`:
  - Pre-check: Spark anti-join `bronze.match_ids` vs `bronze.match_raw` on `match_id`
    to get `new_match_ids` (avoids wasting API quota on already-ingested matches)
  - For each new `match_id`: fetches `/matches/{matchId}` (using regional host)
  - Stores `match_id` (extracted from `metadata.matchId`), full `raw_json STRING`,
    `platform_id` (from `info.platformId`), `game_creation BIGINT`
  - MERGE writes on `match_id` (`WHEN NOT MATCHED THEN INSERT *`)
  - `_batch_id` UUID enables per-batch Silver replay
- All three tables: Delta format, UC three-part names, NO DBFS paths, NO Hive Metastore
- `bronze.ingestion_log` table updated after each job run:
  `(batch_id, run_start, run_end, requests_made, count_429, new_matches_ingested, status)`

**Volume estimate documented**: KR Challenger + Grandmaster cold run ≈ 6,000-10,000 API calls
at 100 req/2min sustained = 2-3.5 hours; DAB `timeout_seconds: 14400` set in job YAML.

**Acceptance**: After a real job run against dev workspace:
```sql
SELECT COUNT(*) FROM lol_analytics.bronze.match_raw;  -- > 0
SELECT COUNT(*) FROM lol_analytics.bronze.ingestion_log;  -- 1 row
```
Second run produces identical `COUNT(*)` in `bronze.match_raw` (MERGE idempotency verified).

---

#### Plan 02-04: Bronze Ingestion — Match Timeline, Summoner, and Account (Enrichment Tasks)

**Complexity**: Medium

**Requirements covered**: BRZ-07, BRZ-08, BRZ-09

**Depends on**: Plan 02-03 (`bronze.match_raw` must exist with real `match_id` values)

**Delivers**:
- `src/ingestion/bronze_match_timeline.py`:
  - Reads `match_id` list from `bronze.match_raw` that do NOT yet exist in
    `bronze.match_timeline_raw` (anti-join dedup, same pattern as match raw)
  - Fetches `/matches/{matchId}/timeline` (regional host: `asia` for KR)
  - MERGE writes to `lol_analytics.bronze.match_timeline_raw` on `match_id`
  - Timeline note: large JSON (~28 frames × 10 participants), runs as separate DAB task
    with its own timeout; failure does NOT block match detail pipeline
- `src/ingestion/bronze_summoner.py`:
  - Reads PUUIDs from `bronze.league_entries` not yet in `bronze.summoner_raw`
  - Fetches Summoner-V4 by PUUID (platform routing: `kr.api.riotgames.com`)
  - MERGE writes to `lol_analytics.bronze.summoner_raw` on `puuid`
- `src/ingestion/bronze_account.py`:
  - Reads PUUIDs from `bronze.league_entries` not yet in `bronze.account_raw`
  - Fetches Account-V1 by PUUID (regional routing: `asia.api.riotgames.com`)
  - MERGE writes to `lol_analytics.bronze.account_raw` on `puuid`
- All three tables: Delta format, UC three-part names, `_batch_id` lineage column

**Note on routing**: Summoner-V4 uses PLATFORM routing (`kr.api.riotgames.com`).
Account-V1 uses REGIONAL routing (`asia.api.riotgames.com`). Both handled by `config.py`.

**Acceptance**: All three tables populated with non-zero row counts. Timeline task failure
(intentionally triggered by invalid match ID) does NOT cause summoner or account tasks to fail.

---

#### Plan 02-05: DAB Ingestion Job Definition, Unit Tests, and CI Integration

**Complexity**: Medium

**Requirements covered**: TEST-02, TEST-04

**Depends on**: Plans 02-01, 02-02, 02-03, 02-04

**Delivers**:
- `resources/jobs/ingestion_job.yml` DAB job definition:
  - Job-level parameters: `region` (default: `KR`), `tier` (default: `CHALLENGER`)
  - `timeout_seconds: 14400` (4-hour cold-run budget)
  - Task dependency graph:
    ```
    league_entries_task
         ↓
    match_ids_task
         ↓
    match_raw_task ──────────────────┐
         ↓                           │
    match_timeline_task          summoner_task
    (depends_on: match_raw_task)  (depends_on: match_ids_task — can run in parallel with timeline)
         ↓
    account_task
    (depends_on: summoner_task)
    ```
  - Each task references `new_cluster` (DBR 16.4 LTS, `job_cluster_key: main_cluster`)
  - `run_as` references CI SP app ID
- `tests/unit/test_riot_client.py`: unit tests for `RiotRateLimiter` and `call_riot_api()`:
  - Covers: normal 200 response, 429 with `X-Rate-Limit-Type: application` + `Retry-After`,
    429 with `X-Rate-Limit-Type: service`, 404 raises `RiotApiError`,
    `Retry-After` sleep duration honored, both buckets decremented per call
  - Uses `pytest-mock` to mock `requests.get` and `time.sleep`
- `tests/unit/test_config.py`: covers routing lookups and parameter parsing
- `pytest` runs locally on Linux Mint with `JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64`
  (documented in `docs/setup.md` and `Makefile`)
- CI `ci.yml` runs `pytest tests/unit/ --cov=src --cov-report=xml` — coverage report uploaded

**Acceptance**: `make test` passes locally; CI `ci.yml` green on push.

**LinkedIn deliverable**: Phase 2 article + short post committed to
`docs/posts/phase-2-article.md` and `docs/posts/phase-2-post.md`

---

### Phase 3: Silver Transformation Layer

**Goal**: Parse all Bronze raw JSON strings into typed, schema-enforced, Liquid Clustered Delta
tables using explicit `StructType` definitions built from real Bronze data, with every
transformation function covered by local PySpark unit tests using `chispa`.

**Depends on**: Phase 2 (Bronze tables populated with real KR Challenger data —
`schemas/match_schema.py` cannot be written correctly without a real API response)

**Requirements**: SLV-01, SLV-02, SLV-03, SLV-04, SLV-05, SLV-06, SLV-07, SLV-08, SLV-09,
SLV-10, SLV-11, SLV-12, SLV-13, TEST-01, TEST-03, TEST-05

**Success Criteria** (what must be TRUE):
  1. `SELECT COUNT(*) FROM lol_analytics.silver.match_participants` returns 10× the row count
     of `bronze.match_raw` (one row per participant per match, exploded correctly)
  2. `DESCRIBE TABLE lol_analytics.silver.match_participants` shows no STRUCT columns —
     `challenges` is fully flattened to 125 individual `chal_*` prefix columns
  3. Re-running the Silver transformation job produces identical row counts (MERGE WITH SCHEMA
     EVOLUTION is idempotent — no duplicates on second run)
  4. `pytest tests/unit/ -v` passes locally on Linux Mint with zero live cluster dependency,
     covering all Silver transformation functions with `chispa` DataFrame assertions
  5. `DESCRIBE TABLE lol_analytics.silver.match` shows `CLUSTER BY` (Liquid Clustering) on
     the primary query key — not `PARTITIONED BY`

**Plans**: 5 plans

Plans:
- [ ] 03-01: `schemas/match_schema.py` — StructType definitions from real Bronze data
- [ ] 03-02: Silver match transformations — `silver.match`, `silver.match_participants`, `silver.match_teams`, `silver.match_teams_bans`, `silver.match_teams_objectives`
- [ ] 03-03: Silver timeline transformations — `silver.match_timeline_frames`, `silver.match_timeline_participant_frames`, `silver.match_timeline_events`
- [ ] 03-04: Silver league entries transformation — `silver.league_entries`
- [ ] 03-05: Unit tests, test fixtures, coverage report, and Silver DAB job definition

**UI hint**: no

---

#### Plan 03-01: `schemas/match_schema.py` — StructType Definitions from Real Bronze Data

**Complexity**: Complex

**Requirements covered**: SLV-01

**Depends on**: Phase 2 complete (`bronze.match_raw` populated with real KR Challenger data)

**Critical blocking dependency**: This plan is the gate for all Silver transformation plans.
No Silver code can be written until the StructType is validated against real API responses.

**Delivers**:
- Capture a real KR Challenger match JSON from `bronze.match_raw`:
  ```python
  sample = spark.table("lol_analytics.bronze.match_raw").limit(1) \
                .select("raw_json").collect()[0][0]
  inferred = spark.read.json(spark.sparkContext.parallelize([sample])).schema
  ```
  Use `schema_of_json` output as a BASELINE only — do NOT use it as the production schema.
- `schemas/match_schema.py` with explicit, version-controlled `StructType` constants:
  - `MATCH_SCHEMA: StructType` — top-level match JSON (metadata + info)
  - `PARTICIPANT_SCHEMA: StructType` — full 147-field participant struct
  - `CHALLENGE_FIELDS: list[str]` — 125 challenge field names (validated against real response,
    not community sources alone); fields mapped to `chal_` prefix in Silver
  - `TEAMS_SCHEMA: StructType` — teams array element (teamId, win, bans, feats, objectives)
- `schemas/timeline_schema.py` with:
  - `TIMELINE_SCHEMA: StructType` — top-level timeline JSON (metadata + info.frames)
  - `FRAME_SCHEMA: StructType` — individual frame (timestamp, participantFrames map, events)
  - `CHAMPION_STATS_FIELDS: list[str]` — 25 championStats fields
  - `DAMAGE_STATS_FIELDS: list[str]` — 12 damageStats fields
- Both schema files are pure Python constants — zero Spark imports at module level
  (enables `import schemas.match_schema` in tests without SparkSession)
- `tests/unit/test_schemas.py`: validates field counts match documentation:
  `assert len(CHALLENGE_FIELDS) == 125`, `assert len(CHAMPION_STATS_FIELDS) == 25`

**Research flag**: CHALLENGE_FIELDS has MEDIUM confidence from community sources.
Validate ALL 125 field names against the real KR Challenger match response during this plan.
Update `schemas/match_schema.py` accordingly before writing transformers.

**Acceptance**: `from schemas.match_schema import MATCH_SCHEMA, CHALLENGE_FIELDS` imports
without error; `len(CHALLENGE_FIELDS) == 125` asserts true against a real response.

---

#### Plan 03-02: Silver Match Transformations

**Complexity**: Complex

**Requirements covered**: SLV-02, SLV-03, SLV-04, SLV-05, SLV-06, SLV-11, SLV-12, SLV-13

**Depends on**: Plan 03-01 (`MATCH_SCHEMA` must be validated)

**Delivers**:
- `src/transformations/silver/match_transformer.py` — pure functions (DataFrame in → out):

  `transform_to_silver_match(bronze_df, match_schema) -> DataFrame`
  - Applies `from_json(col("raw_json"), match_schema)` → parses full match struct
  - Selects flat `info`-level fields: `match_id`, `game_id`, `game_mode`, `game_type`,
    `game_duration_s`, `game_version`, `game_creation_ms`, `game_start_ts_ms`,
    `game_end_ts_ms`, `queue_id`, `platform_id`, `map_id`, `end_of_game_result`
  - Lineage cols: `_ingested_at`, `_region`, `_tier`, `_batch_id`, `_transformed_at`
  - Target: `silver.match` — `CLUSTER BY (match_id)`

  `transform_to_silver_match_participants(bronze_df, match_schema) -> DataFrame`
  - Explodes `info.participants` array → 10 rows per match
  - Selects all 147 flat participant fields with snake_case aliases
  - Flattens `challenges` struct: 125 fields expanded to individual `chal_{field_name}`
    columns (NOT kept as nested struct) — enables Gold GROUP BY on individual metrics
  - Flattens `perks.statPerks` (3 fields) and `perks.selections` (array, flattened inline)
  - Flattens `missions` (12 fields inline), `playerAugment*` fields, `PlayerBehavior` fields
  - Target: `silver.match_participants` — `CLUSTER BY (match_id, champion_id)`
  - Idempotent MERGE ON `(match_id, participant_id)`

  `transform_to_silver_match_teams(bronze_df, match_schema) -> DataFrame`
  - From parsed teams array: `match_id`, `team_id`, `win`, `feats` (flattened)
  - Target: `silver.match_teams` — `CLUSTER BY (match_id, team_id)`

  `transform_to_silver_match_teams_bans(bronze_df, match_schema) -> DataFrame`
  - Uses `inline(teams.bans)` to explode bans array-of-struct into one row per ban
  - Columns: `match_id`, `team_id`, `champion_id`, `pick_turn`
  - Target: `silver.match_teams_bans` — `CLUSTER BY (match_id, champion_id)`

  `transform_to_silver_match_teams_objectives(bronze_df, match_schema) -> DataFrame`
  - Pivots `teams.objectives` struct (baron, dragon, tower, etc.) to rows
  - One row per objective type per team: `match_id`, `team_id`, `objective_type`,
    `first` (boolean), `kills` (int)
  - Target: `silver.match_teams_objectives` — `CLUSTER BY (match_id, team_id)`

- All writes use Delta MERGE with `withSchemaEvolution()`:
  ```python
  (DeltaTable.forName(spark, "lol_analytics.silver.match")
    .merge(df, "target.match_id = source.match_id")
    .whenNotMatchedInsertAll()
    .withSchemaEvolution()
    .execute())
  ```

**Key constraint**: `challenges` must be flat `chal_*` columns — NOT a nested STRUCT.
Gold aggregations group by champion and average individual challenge metrics.

**Acceptance**: `SELECT COUNT(*) FROM silver.match_participants` = 10× `COUNT(*) FROM bronze.match_raw`
(10 participants per match). `DESCRIBE TABLE silver.match_participants` shows no STRUCT columns.

---

#### Plan 03-03: Silver Timeline Transformations

**Complexity**: Complex

**Requirements covered**: SLV-07, SLV-08, SLV-09, SLV-11, SLV-12, SLV-13

**Depends on**: Plan 03-01 (`TIMELINE_SCHEMA` must be validated)

**Note**: Timeline ingestion (Phase 2, `bronze.match_timeline_raw`) must be complete
before this plan can produce non-trivial results.

**Delivers**:
- `src/transformations/silver/timeline_transformer.py` — pure functions:

  `transform_to_silver_timeline_frames(bronze_df, timeline_schema) -> DataFrame`
  - Applies `from_json(col("raw_json"), timeline_schema)`
  - Explodes `info.frames` array → one row per frame
  - Columns: `match_id`, `frame_index`, `timestamp_ms`
  - Target: `silver.match_timeline_frames` — `CLUSTER BY (match_id)`

  `transform_to_silver_timeline_participant_frames(bronze_df, timeline_schema) -> DataFrame`
  - Two-level explosion:
    1. Explode `info.frames[]` → frame rows
    2. Explode `frame.participantFrames{}` (map, key = participant_id STRING) →
       one row per participant per frame
  - Flattens `championStats` (25 fields), `damageStats` (12 fields) inline
  - Columns: `match_id`, `frame_index`, `participant_id`, `timestamp_ms`,
    `position_x`, `position_y`, `current_gold`, `total_gold`, `xp`, `level`,
    `minions_killed`, `jungle_minions_killed`, `time_enemy_spent_controlled`,
    + all 25 champion stat fields, + all 12 damage stat fields
  - Target: `silver.match_timeline_participant_frames` — `CLUSTER BY (match_id, participant_id)`

  `transform_to_silver_timeline_events(bronze_df, timeline_schema) -> DataFrame`
  - Explodes `frame.events[]` array → one row per event per frame
  - Columns: `match_id`, `frame_index`, `event_type`, `timestamp_ms`, `real_timestamp_ms`,
    `participant_id`, `killer_id`, `victim_id`, `assisting_participant_ids` (array),
    `item_id`, `skill_slot`, `level_up_type`, `ward_type`, `building_type`, `lane_type`,
    `position_x`, `position_y`
  - Nullable-friendly: not all event types have all fields
  - Target: `silver.match_timeline_events` — `CLUSTER BY (match_id, event_type)`

- All three tables: MERGE with `withSchemaEvolution()`, Liquid Clustering

**Acceptance**: `SELECT DISTINCT event_type FROM silver.match_timeline_events` returns
expected event types (CHAMPION_KILL, ITEM_PURCHASED, SKILL_LEVEL_UP, etc.).

---

#### Plan 03-04: Silver League Entries Transformation

**Complexity**: Simple

**Requirements covered**: SLV-10, SLV-11, SLV-12, SLV-13

**Depends on**: Plan 03-01 (schema patterns established; league entries StructType simpler
than match — can proceed in parallel with 03-02 after 03-01 complete)

**Delivers**:
- `src/transformations/silver/league_transformer.py`:

  `transform_to_silver_league_entries(bronze_df) -> DataFrame`
  - Parses `raw_json` using a `LEAGUE_ENTRY_SCHEMA` defined in `schemas/league_schema.py`
  - Typed columns: `summoner_id STRING`, `puuid STRING`, `summoner_name STRING`,
    `tier STRING`, `rank STRING`, `league_points INT`, `wins INT`, `losses INT`,
    `veteran BOOLEAN`, `inactive BOOLEAN`, `fresh_blood BOOLEAN`, `hot_streak BOOLEAN`,
    `queue_type STRING`, `_region STRING`, `_tier STRING`
  - Computed column: `win_rate DOUBLE` = `wins / (wins + losses)` (null-safe)
  - Target: `silver.league_entries` — `CLUSTER BY (tier, rank, _region)`
  - MERGE ON `(puuid, _region, _tier, _ingested_at)` with schema evolution

**Acceptance**: `SELECT tier, rank, AVG(win_rate) FROM silver.league_entries GROUP BY 1, 2`
returns plausible values (Challenger should have ~60%+ win rates for top players).

---

#### Plan 03-05: Unit Tests, Test Fixtures, Coverage Report, and Silver DAB Job Definition

**Complexity**: Medium

**Requirements covered**: TEST-01, TEST-03, TEST-04, TEST-05

**Depends on**: Plans 03-01, 03-02, 03-03, 03-04

**Delivers**:
- `tests/conftest.py` — session-scoped `SparkSession` fixture:
  ```python
  SparkSession.builder.master("local[1]").appName("test_suite")
    .config("spark.sql.shuffle.partitions", "1")
    .config("spark.driver.bindAddress", "127.0.0.1")
  ```
  Delta support: `.config("spark.jars.packages", "io.delta:delta-spark_2.12:3.3.2")`
- `tests/unit/fixtures/` directory with minimal JSON samples:
  - `sample_match.json` — 1 match with 10 participants, minimal required fields populated
  - `sample_match_minimal_participants.json` — 2 participants for fast assertion tests
  - `sample_timeline.json` — 3 frames with participantFrames populated
  - `sample_league_entries.json` — 5 entries
  - Note: `challenges` fixture must include all 125 fields (even if null) to test full flatten
- `tests/unit/test_match_transformer.py`:
  - `test_transform_to_silver_match`: asserts row count, column names, no nulls in required cols
  - `test_transform_to_silver_match_participants`: row count = 10× input matches;
    no STRUCT columns; all `chal_*` columns present with correct count (125)
  - `test_flatten_challenges_isolation`: tests `flatten_challenges()` pure function in isolation
  - `test_transform_to_silver_match_teams_bans`: bans array exploded correctly
  - `test_transform_to_silver_match_teams_objectives`: pivot produces expected objective types
  - Uses `chispa.assert_df_equality` for row-level diff assertions
- `tests/unit/test_timeline_transformer.py`:
  - `test_transform_to_silver_timeline_frames`: row count = frames count × match count
  - `test_transform_to_silver_timeline_participant_frames`: row count = frames × 10 participants
  - `test_transform_to_silver_timeline_events`: event rows per frame correct
- `tests/unit/test_schemas.py`:
  - `assert len(CHALLENGE_FIELDS) == 125`
  - `assert len(CHAMPION_STATS_FIELDS) == 25`
  - `assert len(DAMAGE_STATS_FIELDS) == 12`
  - Field name smoke test: spot-check known fields present
- `resources/jobs/transformation_job.yml` DAB job definition:
  - Two tasks: `silver_match_task` and `silver_timeline_task` (can run in parallel)
  - A third task `silver_league_task` (depends_on: nothing — independent source)
  - Each task references `new_cluster` with DBR 16.4 LTS
  - `run_as` references CI SP
- CI `ci.yml` updated: `pytest tests/unit/ --cov=src --cov-report=xml --cov-fail-under=70`
  (70% minimum coverage enforced)

**Acceptance**: `make test` passes locally; coverage report shows ≥70% across `src/`;
`ci.yml` CI passes with coverage artifact uploaded.

**LinkedIn deliverable**: Phase 3 article + short post committed to
`docs/posts/phase-3-article.md` and `docs/posts/phase-3-post.md`

---

### Phase 4: Gold Analytics Layer

**Goal**: Aggregate validated Silver tables into three queryable Gold Delta tables — champion
performance, pick/ban rates, and tier distribution — all reading exclusively from Silver,
deployable via DABs, and queryable in under 5 seconds from Databricks SQL.

**Depends on**: Phase 3 (Silver tables must be stable; Gold column references break if Silver
schema changes — do not start Gold until Silver is fully validated)

**Requirements**: GOLD-01, GOLD-02, GOLD-03, GOLD-04

**Success Criteria** (what must be TRUE):
  1. `SELECT champion_name, AVG(avg_kda), AVG(win_rate) FROM gold.champion_performance GROUP BY 1
     ORDER BY 2 DESC LIMIT 10` returns plausible top-10 KDA champions in under 5 seconds
  2. `gold.pick_ban_rates` contains rows for the current patch with non-zero `pick_rate` and
     `ban_rate` for the top champions — verifiable against known KR Challenger meta
  3. `gold.tier_distribution` contains rows for all Challenger and Grandmaster rank entries
     from `silver.league_entries` with correct `avg_lp` values
  4. Gold tables read ONLY from Silver — zero `FROM bronze.*` references in any Gold job code
  5. Re-running the Gold job is idempotent — row counts are identical on second run
     (MERGE or `CREATE OR REPLACE` pattern used, not raw `INSERT`)

**Plans**: 3 plans

Plans:
- [ ] 04-01: `gold.champion_performance` and `gold.tier_distribution`
- [ ] 04-02: `gold.pick_ban_rates`
- [ ] 04-03: Gold DAB job definition and end-to-end validation query

**UI hint**: no

---

#### Plan 04-01: `gold.champion_performance` and `gold.tier_distribution`

**Complexity**: Medium

**Requirements covered**: GOLD-01, GOLD-03, GOLD-04

**Depends on**: Phase 3 complete (Silver tables populated and validated)

**Delivers**:
- `src/transformations/gold/champion_performance.py`:

  `build_gold_champion_performance(spark) -> DataFrame`
  - Reads from `silver.match_participants` and `silver.match`
  - Join: `silver.match_participants.match_id = silver.match.match_id`
  - Aggregates at grain: `(champion_id, champion_name, individual_position, platform_id,
    game_version, _tier)`
  - Computed metrics:
    - `games_played = COUNT(*)`
    - `wins = SUM(CASE WHEN win THEN 1 ELSE 0 END)`
    - `win_rate = wins / games_played`
    - `avg_kills = AVG(kills)`, `avg_deaths = AVG(deaths)`, `avg_assists = AVG(assists)`
    - `avg_kda = AVG((kills + assists) / NULLIF(deaths, 0))`
    - `avg_damage_to_champions = AVG(total_damage_dealt_to_champions)`
    - `avg_gold_earned = AVG(gold_earned)`
    - `avg_cs = AVG(total_minions_killed + neutral_minions_killed)`
    - `avg_game_duration_s = AVG(silver.match.game_duration_s)`
  - Write: `CREATE OR REPLACE TABLE lol_analytics.gold.champion_performance AS SELECT ...`
    (full rebuild acceptable at Gold — dataset is aggregated, not raw)
  - `CLUSTER BY (champion_id, game_version)`

- `src/transformations/gold/tier_distribution.py`:

  `build_gold_tier_distribution(spark) -> DataFrame`
  - Reads from `silver.league_entries`
  - Aggregates at grain: `(tier, rank, _region)`
  - Columns: `player_count = COUNT(DISTINCT puuid)`, `avg_lp = AVG(league_points)`,
    `avg_win_rate = AVG(win_rate)`, `total_wins = SUM(wins)`, `total_losses = SUM(losses)`
  - Write: `CREATE OR REPLACE TABLE lol_analytics.gold.tier_distribution`
  - `CLUSTER BY (tier, rank)`

**Acceptance**: Both tables populated; `SELECT COUNT(*) FROM gold.champion_performance` > 100
(many champions × positions × patches).

---

#### Plan 04-02: `gold.pick_ban_rates`

**Complexity**: Medium

**Requirements covered**: GOLD-02, GOLD-04

**Depends on**: Phase 3 complete (`silver.match_participants` and `silver.match_teams_bans`
and `silver.match` must be populated)

**Depends on plan**: 04-01 (reuses `game_count` calculation pattern established there)

**Delivers**:
- `src/transformations/gold/pick_ban_rates.py`:

  `build_gold_pick_ban_rates(spark) -> DataFrame`
  - Reads from: `silver.match_participants`, `silver.match_teams_bans`, `silver.match`
  - Total games per `(game_version, platform_id, _tier)`:
    `total_games = COUNT(DISTINCT match_id) FROM silver.match GROUP BY game_version, ...`
  - Pick counts: `COUNT(*) FROM silver.match_participants GROUP BY champion_id, game_version`
  - Ban counts: `COUNT(*) FROM silver.match_teams_bans GROUP BY champion_id, match_id` then
    `COUNT(DISTINCT match_id)` where champion was banned
  - Computed: `pick_rate = pick_count / (total_games * 10.0)` (10 participants per match)
  - Computed: `ban_rate = ban_count / total_games` (typically 5 bans per team = 10 per match)
  - Columns: `champion_id`, `game_version`, `platform_id`, `_tier`, `games_played`,
    `pick_count`, `ban_count`, `pick_rate`, `ban_rate`, `presence_rate` (pick + ban)
  - Write: `CREATE OR REPLACE TABLE lol_analytics.gold.pick_ban_rates`
  - `CLUSTER BY (champion_id, game_version)`

**Acceptance**: `SELECT champion_id, pick_rate, ban_rate FROM gold.pick_ban_rates
WHERE ban_rate > 0.5 ORDER BY ban_rate DESC LIMIT 5` returns known high-ban champions
in the current KR Challenger meta.

---

#### Plan 04-03: Gold DAB Job Definition and End-to-End Validation Query

**Complexity**: Simple

**Requirements covered**: GOLD-04

**Depends on**: Plans 04-01, 04-02

**Delivers**:
- `resources/jobs/gold_job.yml` DAB job definition:
  - Three tasks: `champion_performance_task`, `tier_distribution_task` (can run in parallel),
    `pick_ban_rates_task` (depends_on: none — independent from performance task)
  - Each task: `new_cluster` with DBR 16.4 LTS, `run_as` CI SP
- `notebooks/gold/validation_queries.py` — a notebook with showcase queries:
  - Top 10 champions by KDA this patch (Challenger KR)
  - Top 10 banned champions this patch
  - Tier distribution bar (Challenger vs Grandmaster LP spread)
  - This notebook is the "recruiter demo" query — must run end-to-end in < 5 minutes
- `Makefile` target: `make run-gold` = `databricks bundle run gold_job --target dev`
- `docs/architecture_diagram.md` updated with Gold layer data flow

**Acceptance**: Running `make run-gold` completes successfully; all three Gold tables have
correct row counts; `validation_queries.py` notebook runs end-to-end on dev workspace
without errors.

**LinkedIn deliverable**: Phase 4 article + short post committed to
`docs/posts/phase-4-article.md` and `docs/posts/phase-4-post.md`

---

### Phase 5: Portfolio Polish, MCP Showcase & LinkedIn Posts

**Goal**: Ship a portfolio-ready project that a recruiter can run end-to-end in under 30
minutes — complete with a compelling README, a working MCP integration showing Claude
interacting with the live workspace, a Makefile that hides all complexity, and the full
LinkedIn content series.

**Depends on**: Phase 4 (all pipeline layers must be stable and validated before documentation
can be accurate)

**Requirements**: AGTC-01, AGTC-02, AGTC-03, AGTC-04

**Success Criteria** (what must be TRUE):
  1. A developer who has never seen this project can clone the repo, follow `README.md`,
     and have the pipeline running in their own dev workspace within 30 minutes
  2. `make setup && make test && make deploy-dev` completes without errors on a fresh clone
     (all prereqs documented; no magic steps hidden outside the Makefile)
  3. The MCP configuration in `docs/mcp-setup.md` lets Claude list tables, run jobs, and
     query Silver data directly from the Claude Code session — demonstrable in a screen recording
  4. All 5 LinkedIn post pairs (one per phase) are committed to `docs/posts/` and accurately
     describe what was built with specific technical details (not marketing fluff)

**Plans**: 3 plans

Plans:
- [ ] 05-01: `README.md`, architecture diagram, and 30-minute quickstart
- [ ] 05-02: `Makefile` polish and `ai-dev-kit` MCP configuration
- [ ] 05-03: LinkedIn post series finalization and portfolio self-audit

**UI hint**: no

---

#### Plan 05-01: `README.md`, Architecture Diagram, and 30-Minute Quickstart

**Complexity**: Medium

**Requirements covered**: AGTC-02

**Depends on**: Phase 4 complete (accurate descriptions require a working pipeline)

**Delivers**:
- `README.md` sections:
  - **What this is**: 2-sentence project summary targeting DE hiring managers
  - **Architecture diagram**: ASCII or Mermaid diagram showing:
    `Riot API → Bronze (raw JSON) → Silver (typed/flat) → Gold (aggregated) → SQL/Analytics`
    with UC catalog names and GitHub Actions CI/CD lane
  - **Tech stack table**: DBR 16.4 LTS, DABs, Python 3.12, Delta Lake, Unity Catalog,
    GitHub Actions OIDC
  - **Quickstart (< 30 min)**: numbered steps covering prerequisites (Azure subscription,
    Databricks workspace, Riot API key), repo clone, `make setup`, `make deploy-dev`,
    `databricks bundle run ingestion_job --target dev`
  - **How Claude built this**: section documenting the agentic workflow — Claude Code +
    ai-dev-kit MCP used to design schemas, write transformation logic, validate Silver output,
    iterate on Gold queries; includes specific examples of MCP tool calls
  - **Project structure**: annotated directory tree matching PITFALLS.md recommendation
  - **CI/CD pipeline**: diagram of the 3-workflow GitHub Actions setup
  - **Data model**: table of all Bronze/Silver/Gold tables with row grain and key columns
  - **Running locally**: `make test` instructions with Java 11 prerequisite note
- `docs/architecture_diagram.md` — detailed data flow diagram for the article

**Acceptance**: A peer reads `README.md` cold and can set up the project without asking
any questions.

---

#### Plan 05-02: `Makefile` Polish and `ai-dev-kit` MCP Configuration

**Complexity**: Medium

**Requirements covered**: AGTC-01, AGTC-03

**Depends on**: Plan 05-01

**Delivers**:
- `Makefile` with complete, documented targets:
  - `make setup` — creates venv, installs `requirements-dev.txt`, sets `JAVA_HOME` hint
  - `make test` — runs `pytest tests/unit/ -v --cov=src`
  - `make validate` — runs `databricks bundle validate`
  - `make deploy-dev` — runs `databricks bundle deploy --target dev`
  - `make deploy-prod` — runs `databricks bundle deploy --target prod` (requires tag)
  - `make run-ingestion` — `databricks bundle run ingestion_job --target dev`
  - `make run-silver` — `databricks bundle run transformation_job --target dev`
  - `make run-gold` — `databricks bundle run gold_job --target dev`
  - `make smoke` — runs smoke test job on dev
  - `make clean` — removes `__pycache__`, `.pytest_cache`, `htmlcov/`
  - Each target has a `## Comment` for `make help` output
- `docs/mcp-setup.md` — configuration guide for `ai-dev-kit` MCP:
  - How to install and configure `ai-dev-kit` in Claude Code settings
  - MCP tool examples:
    - `list_tables(catalog="lol_analytics", schema="silver")` — show all Silver tables
    - `run_job(job_name="ingestion_job", parameters={"region": "KR", "tier": "CHALLENGER"})`
    - `execute_sql("SELECT champion_name, win_rate FROM gold.champion_performance ORDER BY win_rate DESC LIMIT 10")`
  - Screen recording script: 5-step demo flow from Claude Code session
- `.claude/` directory or `CLAUDE.md` if needed for Claude Code project context
- `docs/posts/` directory structure: `phase-{1..5}-article.md`, `phase-{1..5}-post.md`

**Acceptance**: `make help` prints all targets with descriptions; MCP configuration
documented sufficiently to reproduce in under 15 minutes.

---

#### Plan 05-03: LinkedIn Post Series Finalization and Portfolio Self-Audit

**Complexity**: Simple

**Requirements covered**: AGTC-04

**Depends on**: Plans 05-01, 05-02

**Delivers**:
- All 5 LinkedIn post pairs finalized and committed (articles already drafted per phase;
  this plan reviews, polishes, and confirms technical accuracy against the actual code):
  - `docs/posts/phase-1-article.md` — "Building enterprise CI/CD for a Databricks project
    from day zero: OIDC, Unity Catalog ownership, and why I never touched a PAT token"
  - `docs/posts/phase-1-post.md` — 150-word summary with key takeaway
  - `docs/posts/phase-2-article.md` — "How I built a production Riot Games API ingester:
    dual-bucket rate limiting, routing gotchas, and Delta MERGE idempotency"
  - `docs/posts/phase-2-post.md`
  - `docs/posts/phase-3-article.md` — "Flattening 147 fields and 125 nested challenges:
    PySpark Silver transformation design with 100% local test coverage"
  - `docs/posts/phase-3-post.md`
  - `docs/posts/phase-4-article.md` — "Gold layer analytics on 6,000 KR Challenger matches:
    champion KDA, pick/ban rates, and Liquid Clustering at scale"
  - `docs/posts/phase-4-post.md`
  - `docs/posts/phase-5-article.md` — "The agentic data engineer: how Claude Code + MCP
    built a production Databricks pipeline end-to-end"
  - `docs/posts/phase-5-post.md`
- Portfolio self-audit checklist verified:
  - [ ] `make setup && make test` passes on a fresh clone (tested in clean venv)
  - [ ] `databricks bundle validate` passes
  - [ ] `README.md` quickstart steps accurate (tested step-by-step)
  - [ ] All UC table three-part names correct (no `hive_metastore` references)
  - [ ] No secrets or API keys in any committed file (`git log --all -S "riot"` clean)
  - [ ] `pytest tests/unit/` passes with ≥70% coverage
  - [ ] All 47 v1 requirements have observable evidence of completion

**Acceptance**: All 10 LinkedIn files committed to `docs/posts/`; self-audit checklist
100% checked; `README.md` is the single entry point a recruiter needs.

**LinkedIn deliverable**: Phase 5 article + short post committed to
`docs/posts/phase-5-article.md` and `docs/posts/phase-5-post.md`

---

## Progress

**Execution Order**: Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

**Within-phase parallelism**:
- Phase 2: Plans 02-03 and 02-04 are sequential by design (timeline depends on match_raw
  match IDs); summoner/account tasks can run in parallel with timeline after match_raw
- Phase 3: Plans 03-02, 03-03, 03-04 can proceed in parallel after 03-01 completes
- Phase 4: Plans 04-01 and 04-02 can proceed in parallel

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure, Governance & CI/CD Foundation | 1/4 | In Progress|  |
| 2. Bronze Ingestion Pipeline | 0/5 | Not started | - |
| 3. Silver Transformation Layer | 0/5 | Not started | - |
| 4. Gold Analytics Layer | 0/3 | Not started | - |
| 5. Portfolio Polish, MCP Showcase & LinkedIn Posts | 0/3 | Not started | - |

**Total plans: 20**

---

## Coverage Validation

All 47 v1 requirements mapped — no orphans.

| Requirement | Phase | Plan |
|-------------|-------|------|
| INFRA-01 | Phase 1 | 01-01 |
| INFRA-02 | Phase 1 | 01-03 |
| INFRA-03 | Phase 1 | 01-03 |
| INFRA-04 | Phase 1 | 01-01 |
| INFRA-05 | Phase 1 | 01-03 |
| INFRA-06 | Phase 1 | 01-04 |
| INFRA-07 | Phase 1 | 01-01 |
| CICD-01 | Phase 1 | 01-02 |
| CICD-02 | Phase 1 | 01-02 |
| CICD-03 | Phase 1 | 01-02 |
| CICD-04 | Phase 1 | 01-02 |
| CICD-05 | Phase 1 | 01-02 |
| CICD-06 | Phase 1 | 01-02 |
| BRZ-01 | Phase 2 | 02-01 |
| BRZ-02 | Phase 2 | 02-02 |
| BRZ-03 | Phase 2 | 02-02 |
| BRZ-04 | Phase 2 | 02-03 |
| BRZ-05 | Phase 2 | 02-03 |
| BRZ-06 | Phase 2 | 02-03 |
| BRZ-07 | Phase 2 | 02-04 |
| BRZ-08 | Phase 2 | 02-04 |
| BRZ-09 | Phase 2 | 02-04 |
| BRZ-10 | Phase 2 | 02-03 |
| TEST-02 | Phase 2 | 02-05 |
| TEST-04 | Phase 2 | 02-05 |
| SLV-01 | Phase 3 | 03-01 |
| SLV-02 | Phase 3 | 03-02 |
| SLV-03 | Phase 3 | 03-02 |
| SLV-04 | Phase 3 | 03-02 |
| SLV-05 | Phase 3 | 03-02 |
| SLV-06 | Phase 3 | 03-02 |
| SLV-07 | Phase 3 | 03-03 |
| SLV-08 | Phase 3 | 03-03 |
| SLV-09 | Phase 3 | 03-03 |
| SLV-10 | Phase 3 | 03-04 |
| SLV-11 | Phase 3 | 03-02 |
| SLV-12 | Phase 3 | 03-02 |
| SLV-13 | Phase 3 | 03-02 |
| TEST-01 | Phase 3 | 03-05 |
| TEST-03 | Phase 3 | 03-05 |
| TEST-05 | Phase 3 | 03-05 |
| GOLD-01 | Phase 4 | 04-01 |
| GOLD-02 | Phase 4 | 04-02 |
| GOLD-03 | Phase 4 | 04-01 |
| GOLD-04 | Phase 4 | 04-03 |
| AGTC-01 | Phase 5 | 05-02 |
| AGTC-02 | Phase 5 | 05-01 |
| AGTC-03 | Phase 5 | 05-02 |
| AGTC-04 | Phase 1–5 | 01-04, 02-05, 03-05, 04-03, 05-03 |

**Mapped: 47/47 ✓**

---

## Critical Path Summary

```
Phase 1 (all plans sequential: 01-01 → 01-02 → 01-03 → 01-04)
    ↓
Phase 2
  02-01 (rate limiter) + 02-02 (config) [parallel]
    ↓
  02-03 (core ingestion chain: league → match_ids → match_raw) [BLOCKING: sequential]
    ↓
  02-04 (timeline + summoner + account) [can run after 02-03]
    ↓
  02-05 (DAB job + tests) [consolidation]
    ↓
Phase 3
  03-01 (schema definitions — GATE for all Silver plans)
    ↓
  03-02 (match transforms)
  03-03 (timeline transforms)   [these three run in parallel after 03-01]
  03-04 (league transforms)
    ↓ (all complete)
  03-05 (tests + DAB job)
    ↓
Phase 4
  04-01 + 04-02 [parallel]
    ↓
  04-03 (Gold DAB job + validation)
    ↓
Phase 5
  05-01 → 05-02 → 05-03
```

**Single-path bottlenecks**:
- INFRA-03 (SP schema ownership) before any Bronze table creation — enforced by Phase 1 ordering
- Real Bronze data before `schemas/match_schema.py` — enforced by Phase 2 before Phase 3
- `schemas/match_schema.py` (`SLV-01`) before ALL Silver transformation plans

---

*Roadmap created: 2026-04-07*
*Requirements: 47/47 v1 covered*
*Total plans: 20 across 5 phases*
