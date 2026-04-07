# Project Research Summary

**Project:** dbx-mls — Databricks Modern Lakehouse (League of Legends)
**Domain:** Batch API ingestion pipeline — Riot Games Match-V5 to Azure Databricks Medallion Architecture
**Researched:** 2026-04-07
**Confidence:** HIGH

---

## Executive Summary

This is a production-grade batch ingestion pipeline that traverses a three-step API hierarchy (League-Exp-V4 seeding → Match-V5 ID collection → Match-V5 detail fetch), writes raw JSON to a Bronze layer in Unity Catalog, and transforms it through Silver into Gold aggregates on Azure Databricks with DABs-managed CI/CD. The defining technical challenge is not Databricks itself — it is the Riot Games API rate limiting model. A Dev key allows only 100 requests per 2 minutes sustained (0.83 req/sec effective), meaning a full cold-run ingest of KR Challenger + Grandmaster (~6,000-10,000 API calls) takes 2-3.5 hours. The entire pipeline must be designed around this constraint: a dual-bucket token bucket rate limiter is mandatory, naive `time.sleep` will cause progressive blacklisting, and the job timeout in DABs must be set accordingly.

The recommended architecture is a well-established Medallion pattern with three cross-cutting design decisions locked in by research: (1) Bronze stores raw JSON as STRING — never parsed at ingest time — making the Bronze layer a replayable archive that survives Riot API schema changes without re-calling the API; (2) Silver uses explicit version-controlled `StructType` definitions in `schemas/match_schema.py` as the single source of truth for parsing, with MERGE as the default write pattern for idempotency and schema evolution via `withSchemaEvolution()`; (3) Liquid Clustering replaces static partitioning for all Silver tables since the dataset stays well under 1 TB and Databricks recommends Liquid Clustering for all new Delta tables as of 2025.

The top systemic risk is the CI/CD and Unity Catalog permissions configuration, which has multiple independent failure modes that compound: OIDC federation policy subject claim mismatches, UC schema ownership being claimed by the wrong identity (developer vs service principal), missing privilege chain grants (USE CATALOG → USE SCHEMA → CREATE TABLE → MODIFY), and DBFS mount patterns from old tutorials being incompatible with Unity Catalog compute. All of these are preventable with correct setup order, but each one fails silently or with cryptic errors. The mitigation is: establish infrastructure and CI/CD in Phase 1 before writing any pipeline code, and deploy all Unity Catalog schemas from CI (never from a local developer machine) from the first deploy forward.

---

## Key Findings

### Recommended Stack

DBR 16.4 LTS (Spark 3.5.2, Python 3.12.3) is the correct runtime. It has a 3-year support window to May 2028, ships Python 3.12.3 (matching the local dev environment), and avoids the Spark 4.0 breaking changes in DBR 17.3 LTS (`input_file_name()` removal, decimal precision changes) that add migration risk with no benefit for a greenfield project. DABs (Declarative Automation Bundles) handle all IaC — workspace provisioning is a one-time manual step. The testing strategy is two-track: unit tests with local PySpark (`pyspark==3.5.2` in `requirements-dev.txt`) using `chispa` for DataFrame assertions, and integration tests run post-deploy against the `dev` target via `databricks bundle run`.

**Core technologies:**

- **DBR 16.4 LTS**: Spark runtime — 3-year LTS support window, Python 3.12.3, avoids Spark 4.0 churn
- **Databricks CLI 0.295.0+**: DABs deployment — native DE IaC tool, what hiring managers expect
- **`requests>=2.32.0`**: Riot API HTTP client — synchronous preferred over async due to Databricks event loop complications
- **`tenacity>=9.0.0`**: Retry logic — de facto Python retry standard, `@retry` decorator for 429 handling
- **`pyspark==3.5.2`** (dev only): Local unit testing — exact match to cluster Spark version eliminates serialization bugs
- **`chispa>=0.9.4`**: DataFrame assertions — descriptive row-level diffs, no live cluster needed
- **`pytest>=8.3.0`**: Test runner — `pytest-cov>=6.0.0` for coverage in CI
- **`delta-spark==3.3.2`** (dev only): Local SparkSession with Delta support for unit tests
- **`databricks-sdk>=0.102.0`**: Workspace API calls, secrets management, CI orchestration
- **`azure-identity>=1.19.0`** (dev/CI only): SP auth for Azure resources from local and CI

### Expected Features

**Must have (table stakes):**

- **Dual-bucket token bucket rate limiter** — Dev key hard caps are 20 req/sec AND 100 req/2min; the 2-minute bucket is the binding constraint (0.83 req/sec sustained); missing it causes progressive blacklisting
- **Retry-After header parsing on 429** — `X-Rate-Limit-Type` determines whether to use `Retry-After` (application/method limits) or exponential backoff (service limits)
- **KR platform → asia regional routing** — Match-V5 endpoints use `asia.api.riotgames.com`, NOT `kr.api.riotgames.com`; wrong host returns 404; encode as a config lookup dict
- **Three-step seeding flow** — League-Exp-V4 (paginate until empty list) → Match-V5 by-puuid (count=20, queue=420) → Match-V5 detail; no shortcut exists
- **Incremental MERGE deduplication on `match_id`** — 10 players share 1 match; pre-check existing IDs before API calls to avoid wasting quota
- **Raw JSON preservation in Bronze** — store verbatim API response as STRING; never parse at Bronze write time; enables full replay when Silver schema evolves
- **Ingestion metadata columns** — `_ingested_at`, `_source_url`, `_region`, `_tier`, `_batch_id` on all Bronze tables
- **Parameterized region and tier** — DAB job parameters (not bundle variables) for runtime configurability

**Should have (differentiators):**

- **`bronze.ingestion_log` operational table** — one row per job run with `requests_made`, `count_429`, `duration_seconds`
- **Header-driven rate limit logging** — parse `X-App-Rate-Limit-Count` response headers and log
- **Separate timeline ingestion DAB task** — timeline JSON is large and expensive; isolating it prevents timeline failures from blocking match detail ingestion
- **`_batch_id` UUID per ingestion run** — enables precise replay: re-run Silver only for batches affected by a schema change

**Defer to Phase 3+ / v2:**

- Summoner-V4 and Account-V1 ingestion (enrichment, not required for match analytics)
- Match-V5 timeline ingestion (Phase 2b after core match pipeline is validated)
- Multi-region simultaneous ingestion
- Streaming / Delta Live Tables migration
- ARAM, Arena, TFT queue types

### Architecture Approach

The Medallion boundary discipline is strict: Bronze is an append-only raw archive (STRING JSON + metadata), Silver is the first and only parsing boundary (explicit `StructType` from `schemas/match_schema.py`, MERGE write pattern, Liquid Clustering), and Gold reads exclusively from Silver. The match participant object (147 fields) is the most complex transformation: `challenges` (125 fields) must be flattened to individual `chal_*` columns in Silver (not kept as STRUCT) because Gold aggregations GROUP BY champion and average individual challenge metrics. The teams layer uses `inline()` on the bans array-of-struct. The timeline layer requires two levels of explosion: `frames[]` (array) → `participantFrames{}` (map, exploded with key=participant_id string) → `championStats` and `damageStats` (flattened inline).

**Major components:**

1. **`src/ingestion/riot_api_client.py`** — dual-bucket rate limiter, `call_riot_api()` with Retry-After handling, `PLATFORM_TO_REGION` routing dict; the only place that calls the Riot API
2. **`src/schemas/match_schema.py` and `timeline_schema.py`** — version-controlled `StructType` definitions; blocking dependency for all Silver jobs; update here first when Riot adds fields
3. **`src/ingestion/bronze_*.py`** — one module per Bronze table; calls API client, writes raw JSON + metadata via MERGE on primary key
4. **`src/transformations/silver/match_transformer.py`** — `from_json` with match schema, `explode(participants)`, `inline(bans)`, objectives pivot; outputs all `silver.match*` tables
5. **`src/transformations/silver/timeline_transformer.py`** — frames explosion, participantFrames map explosion, events explosion; outputs all `silver.match_timeline_*` tables
6. **`resources/`** — DABs YAML: `schemas.yml`, `clusters.yml`, `jobs/ingestion_job.yml`, `jobs/transformation_job.yml`; deployed by CI never by local machine

### Critical Pitfalls

1. **OIDC subject claim mismatch** — the `environment:` key in the GitHub Actions workflow must exactly match the federation policy subject claim (case-sensitive); failure surfaces as `oidc token exchange failed`; set up and validate in Phase 1 before writing any pipeline code
2. **`run_as` does NOT set schema ownership** — DABs `run_as` applies only to job runtime identity, not resource creation; always deploy `prod` (or any shared target) from CI from the very first deploy; a developer deploying first becomes the permanent schema owner
3. **Missing UC privilege chain** — `CREATE TABLE` requires `USE SCHEMA` on parent schema AND `USE CATALOG` on parent catalog; grant the full chain: `USE CATALOG → CREATE SCHEMA → USE SCHEMA → CREATE TABLE → MODIFY → READ/WRITE FILES on external location`; each missing level fails at runtime not at `bundle validate`
4. **2-minute rate limit bucket ignored** — `time.sleep(0.05)` only addresses per-second bucket; the 2-minute bucket (100 req/2min) is exhausted in seconds; use the dual-bucket token bucket from FEATURES.md; wrong host routing (kr vs asia for Match-V5) is an equally silent failure
5. **DBFS mounts incompatible with Unity Catalog compute** — `dbutils.fs.ls("dbfs:/mnt/...")` does not work on UC-enabled clusters; write Bronze directly to UC managed tables via three-part names; never use `dbutils.mount()` or `spark.conf.set("fs.azure.account.key...")`

---

## Cross-Cutting Decisions

These are places where findings from multiple research files interact and constrain each other.

| Decision | Files Involved | Implication |
|----------|---------------|-------------|
| `schemas/match_schema.py` is a hard dependency for Silver | ARCHITECTURE + FEATURES | Must be written and validated against a real API response before Silver transformation can be coded; it blocks the entire Silver phase |
| Synchronous `requests` over async `httpx` | STACK + FEATURES | The dual-bucket rate limiter serializes requests by design; async provides no throughput benefit and adds `nest_asyncio` fragility in Databricks notebooks |
| MERGE as default write pattern for both Bronze and Silver | FEATURES + ARCHITECTURE | Bronze uses MERGE on `match_id`; Silver uses MERGE on `(match_id, participant_id)`; consistent pattern makes every job step idempotent |
| DAB job parameters (not bundle variables) for region/tier | STACK + PITFALLS | Bundle variables are resolved at deploy time and baked in; job parameters are runtime-configurable; using bundle variables for region/tier requires a full redeploy to change |
| Liquid Clustering on Silver, static partitioning acceptable on Bronze | ARCHITECTURE + FEATURES | Bronze tables partition by `(_region, _tier)` — small number of partitions, aligns with query patterns; Silver tables use `CLUSTER BY` — dataset under 1 TB |
| SP must be schema owner from day one | PITFALLS + STACK | Never run `bundle deploy` against `prod` from a local machine; one-time mistake with painful recovery (requires dropping and recreating schemas) |
| `_batch_id` UUID per ingestion run | ARCHITECTURE + FEATURES | Enables Silver replay for individual batches; required for the schema evolution workflow (add field → update schema → reprocess only affected batches) |

---

## Top 5 Risks That Could Derail the Project

**Risk 1: Rate limit blacklisting from Riot Games**
The Riot Dev API key can be temporarily or permanently suspended for rate limit violations. Recovery requires a new key rotated through Databricks Secrets.
Mitigation: Implement the dual-bucket token bucket before the first API call. Test against a single PUUID before running at volume.

**Risk 2: CI/CD service principal permissions incomplete on first prod deploy**
If the SP is missing any level of the UC privilege chain, the deploy fails at runtime. If a developer runs the deploy locally to fix it, they become the schema owner.
Mitigation: Document the full grant script in Phase 1. Run `SHOW GRANTS` verification before the first non-local deploy.

**Risk 3: `schemas/match_schema.py` drift from actual Riot API response**
Silver transformation fails with `from_json` producing null values if the StructType does not match actual JSON. There is no way to build a correct schema without a real API response.
Mitigation: In Phase 2 bronze smoke test, capture a real match JSON and run `schema_of_json` as a baseline, then hand-refine into the explicit StructType. This file is the single highest-value artifact of Phase 3.

**Risk 4: DAB YAML structural errors not caught by `bundle validate`**
`databricks bundle validate` catches config syntax errors but NOT UC permission errors, cluster policy access errors, or runtime Python import errors.
Mitigation: Establish a smoke-test job in Phase 1 that runs a trivial notebook through the full CI/CD pipeline before writing any pipeline code.

**Risk 5: Participant schema complexity causing test maintainability debt**
`silver.match_participants` will be ~272 columns. Unit tests that assert on the full participant transform are brittle.
Mitigation: Use `chispa` with subset column assertions. Build `test_fixtures/` with minimal-field participant JSON samples. Test `flatten_challenges` in isolation from the core participant flatten.

---

## Implications for Roadmap

### Phase 1: Infrastructure and CI/CD Foundation

**Rationale:** Schema ownership is established on first deploy and cannot be cleanly transferred. CI/CD must be proven before any table is created. This phase has zero pipeline dependencies but blocks every other phase.

**Delivers:** Working `databricks.yml` with dev/prod targets, GitHub Actions CI/CD (validate → pytest → deploy-dev on push, deploy-prod on tag), OIDC auth with SP, UC catalog and schemas owned by SP, Databricks Secrets scope with Riot API key, smoke-test job that validates the full deploy path.

**Addresses:** All CI/CD and UC pitfalls (Pitfalls 1-5), DABs YAML structure, secret scope setup.

**Must avoid:** Deploying any DAB target from a local machine. Hardcoding workspace host. Using PAT tokens for CI auth.

**Research flag:** Standard patterns — no additional research needed. PITFALLS.md provides complete setup instructions.

---

### Phase 2: Bronze Ingestion Pipeline

**Rationale:** With infrastructure validated, implement the Riot API client and Bronze ingestion. The rate limiter must be built and tested before any volume API calls. Start with League-Exp-V4 (fewer calls, validates routing and pagination) before Match-V5 (high volume). Timeline ingestion is Phase 2b — separate task, defer until core match pipeline is stable.

**Delivers:** `src/ingestion/riot_api_client.py` (dual-bucket rate limiter, routing dict, Retry-After handling), bronze ingestion for `league_entries`, `match_ids`, and `match_raw` with MERGE deduplication, `bronze.ingestion_log` operational table, unit tests for rate limiter logic, integration smoke test against dev workspace.

**Addresses:** Rate limiting (20 req/sec + 100 req/2min), KR→asia routing, pagination stop condition, match deduplication, raw JSON preservation, `_batch_id` lineage.

**Must avoid:** Parsing JSON at write time. Using `time.sleep(0.05)`. Using `kr.api.riotgames.com` for Match-V5. Fetching timeline inline with match detail.

**Research flag:** Rate limiter implementation is fully specified in FEATURES.md. The only validation needed is a live API call in dev to confirm routing and pagination behavior.

---

### Phase 3: Schema Definition and Silver Transformation

**Rationale:** `schemas/match_schema.py` and `timeline_schema.py` are blocking dependencies for Silver. They must be built from a real KR Challenger match JSON response captured in Phase 2. The Silver transformation logic is complex (147 participant fields, 125 challenges, teams/objectives pivot, timeline map explosion) and benefits from the full Bronze dataset being available for end-to-end testing.

**Delivers:** `src/schemas/match_schema.py` (explicit StructType validated against real API response), `src/schemas/timeline_schema.py`, Silver transformation modules for all `silver.match*` and `silver.match_timeline_*` tables, Liquid Clustering on all Silver tables, UC column tags for identity and PII columns, unit tests using local PySpark + chispa for all transformation functions.

**Addresses:** JSON parsing boundary discipline, `challenges` flattening (125 fields as `chal_*` columns), `inline()` for bans array-of-struct, map explosion for `participantFrames`, MERGE with `withSchemaEvolution()` for idempotent Silver writes.

**Must avoid:** `schema_of_json` or `inferSchema` in production. Keeping `challenges` as a STRUCT in Silver. Using `overwrite` mode on Silver tables. Testing directly against notebooks rather than extracted pure functions.

**Research flag:** Needs validation of the full 147-field participant StructType and 125 challenge field names against a live KR Challenger match response (MEDIUM confidence currently).

---

### Phase 4: Gold Layer and Analytics

**Rationale:** Gold layer design is intentionally deferred until real Silver data patterns are understood. After Phase 3 produces a validated Silver layer, query patterns emerge naturally — which champion/position combinations appear most frequently, which challenge metrics are populated vs null.

**Delivers:** `gold.champion_performance` (champion × position × tier × patch grain), `gold.pick_ban_rates`, `gold.tier_distributions`, DAB gold transformation job, a working dashboard query demonstrating the end-to-end data product.

**Must avoid:** Reading Bronze in Gold jobs. Aggregating before Silver is validated. Building Gold on assumed column names before confirming Silver schema.

**Research flag:** No additional research needed — Gold patterns are standard SQL aggregations on validated Silver tables. ARCHITECTURE.md Section 7 provides the starting point.

---

### Phase 5: Portfolio Polish and LinkedIn Cadence

**Rationale:** Per PROJECT.md, each phase produces a LinkedIn deliverable. Phase 5 consolidates the project for portfolio presentation.

**Delivers:** Complete `README.md` with 30-minute quick-start instructions, `Makefile` with `make test`, `make validate`, `make deploy-dev` shortcuts, ai-dev-kit MCP configuration demonstrating agentic workflow, LinkedIn post series (one per phase).

**Research flag:** Standard patterns — no research needed.

---

### Phase Ordering Rationale

- Infrastructure before pipeline code because schema ownership is established on first deploy and cannot be cleanly transferred
- Bronze before Silver because `schemas/match_schema.py` requires a real API response to be correct; guessing the schema introduces silent null values in Silver
- Match pipeline before timeline because timeline is independently skippable, expensive, and the core analytics value is in match participant data
- Silver fully validated before Gold because Gold aggregation column references break if Silver schema changes
- Portfolio polish last because all phases must be stable before documentation is accurate

---

### Research Flags

**Needs validation during implementation:**
- **Phase 3 (schema definition):** The 125 challenge field names in ARCHITECTURE.md have MEDIUM confidence. Validate `CHALLENGE_FIELDS` list against a real KR Challenger match response before writing the Silver transformer.
- **Phase 2 (rate limiter):** Validate that `X-Rate-Limit-Type` header is present and parsed correctly on a live 429 response before running at volume.

**Standard patterns (skip research-phase):**
- **Phase 1 (infrastructure):** Complete setup instructions in PITFALLS.md. All claims have HIGH confidence official doc sources.
- **Phase 4 (Gold):** Standard SQL aggregations on validated Silver tables.
- **Phase 5 (portfolio):** Documentation and LinkedIn posts.

---

## Confirmed Library Versions

All versions confirmed against PyPI and official docs as of April 2026.

### `requirements.txt` (production cluster dependencies)

```
requests>=2.32.0
tenacity>=9.0.0
databricks-sdk>=0.102.0
```

### `requirements-dev.txt` (local development and CI)

```
-r requirements.txt
pyspark==3.5.2
delta-spark==3.3.2
pytest>=8.3.0
chispa>=0.9.4
pytest-cov>=6.0.0
pytest-mock>=3.14.0
azure-identity>=1.19.0
```

### Tooling (local machine and CI)

| Tool | Version | Purpose |
|------|---------|---------|
| Databricks CLI | 0.295.0+ | DABs deploy, bundle validate |
| Python | 3.12 (matches DBR 16.4 LTS) | Local interpreter — must match cluster Python exactly |
| DBR | 16.4 LTS | Spark 3.5.2, Python 3.12.3, Scala 2.13, support until May 2028 |
| `actions/setup-python` | v5 | GitHub Actions Python setup |
| `databricks/setup-cli` | pin to specific release in prod | Use @main only in upgrade-test workflow |
| `actions/checkout` | v4 | Use `ref: ${{ github.ref }}` to avoid detached HEAD in prod mode |
| Java | 11 (openjdk-11-jdk) | Required for PySpark local mode in unit tests |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against official Microsoft Learn, PyPI, and GitHub releases as of April 2026 |
| Features | HIGH | Rate limits confirmed from Riot Developer Portal; routing mapping verified; Bronze schema design follows official Databricks Medallion pattern |
| Architecture | HIGH | Silver transformation patterns from official PySpark and Delta Lake docs; Liquid Clustering from official Databricks docs March 2026; `challenges` field list MEDIUM — requires live data validation |
| Pitfalls | HIGH | All critical pitfalls verified against official Microsoft Learn and Databricks docs |

**Overall confidence:** HIGH

### Gaps to Address

- **`CHALLENGE_FIELDS` completeness (MEDIUM):** The 125 challenge field names were researched from community sources. Validate against a real KR Challenger match JSON in Phase 2. Use `schema_of_json` on a real response as a baseline for the explicit StructType.
- **Timeline StructType:** `timeline_schema.py` was not fully specified in ARCHITECTURE.md. Build it from a real timeline API response in Phase 2 (same approach as match schema).
- **Dev key vs Production key workflow:** The Riot Dev API key expires every 24 hours. Document the process for obtaining a persistent key in Phase 1 setup and clarify whether a non-expiring personal API key is available.
- **Job timeout configuration:** A full cold-run ingestion takes 2-3.5 hours at Dev key sustained rate. DAB job `timeout_seconds` must be set to at least 14,400 (4 hours).

---

## Sources

### Primary (HIGH confidence)

- [Azure Databricks Runtime release notes — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/) — DBR 16.4 LTS specs
- [Declarative Automation Bundles configuration — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/settings) — YAML schema, run_as behavior
- [GitHub Actions — Azure Databricks — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/github) — CI/CD workflow patterns
- [Enable workload identity federation for GitHub Actions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/provider-github) — OIDC federation setup
- [Manage privileges in Unity Catalog — Databricks docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/) — privilege hierarchy
- [Databricks mounts deprecated — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dbfs/mounts) — DBFS deprecation in UC
- [Delta Lake MERGE — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/delta/merge) — MERGE patterns and withSchemaEvolution
- [Riot Developer Portal — Dev key rate limits](https://developer.riotgames.com/docs/portal) — 20 req/sec, 100 req/2min confirmed
- [databricks-sdk PyPI](https://pypi.org/project/databricks-sdk/) — v0.102.0 as of March 2026
- [Databricks CLI releases — GitHub](https://github.com/databricks/cli/releases) — v0.295.0 as of March 2026
- [tenacity GitHub](https://github.com/jd/tenacity) — actively maintained, Apache 2.0

### Secondary (MEDIUM confidence)

- [Hextechdocs — Rate limiting headers and 429 handling](https://hextechdocs.dev/rate-limiting/) — `X-Rate-Limit-Type` header behavior
- [Riot API routing documentation](https://darkintaqt.com/blog/routing) — platform-to-region mapping
- [MrPowers/chispa — GitHub](https://github.com/MrPowers/chispa) — DataFrame testing library
- [GitHub/RiotGames developer-relations issue #1115](https://github.com/RiotGames/developer-relations/issues/1115) — 10,000 entry cap on league-exp-v4
- [Terraform vs. Databricks Asset Bundles — Alex Ott](https://medium.com/@alexott_en/terraform-vs-databricks-asset-bundles-6256aa70e387) — DABs vs Terraform comparison

---

*Research completed: 2026-04-07*
*Ready for roadmap: yes*
