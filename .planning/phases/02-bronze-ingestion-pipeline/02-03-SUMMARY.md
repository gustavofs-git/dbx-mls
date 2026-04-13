---
phase: 02-bronze-ingestion-pipeline
plan: "03"
subsystem: ingestion
tags: [pyspark, delta, unity-catalog, riot-api, merge, anti-join, databricks-notebooks]

# Dependency graph
requires:
  - phase: 02-01
    provides: RiotRateLimiter, call_riot_api() from src/riot_client.py
  - phase: 02-02
    provides: get_platform_host, get_region_host, get_job_params, RANKED_QUEUE, DEFAULT_MATCH_COUNT from src/config.py
provides:
  - src/ingestion/ package with three bronze ingestion modules
  - ingest_league_entries() — paginated League-Exp-V4 ingest, MERGE on (puuid, _region, _tier)
  - ingest_match_ids() — Match-V5 IDs per PUUID, MERGE on (puuid, match_id)
  - ingest_match_raw() — Match-V5 full detail with LEFT ANTI JOIN pre-check, MERGE on match_id
  - Three DAB notebook entry points (ingest_league_entries, ingest_match_ids, ingest_match_raw)
  - lol_analytics.bronze.ingestion_log with D-06 7-field schema
affects: [02-04, 02-05, silver-transformations]

# Tech tracking
tech-stack:
  added: [pyspark.sql.SparkSession, Delta MERGE INTO, LEFT ANTI JOIN, Unity Catalog three-part names]
  patterns:
    - MERGE INTO with WHEN NOT MATCHED THEN INSERT * for idempotent dedup
    - LEFT ANTI JOIN pre-check to skip already-ingested rows before API calls
    - Driver-side Python for loops for all API calls (no mapPartitions)
    - Staging temp views (_staging_*) as MERGE source
    - sys.path defensive insert in all notebooks for GIT source runtime

key-files:
  created:
    - src/ingestion/__init__.py
    - src/ingestion/bronze_league_entries.py
    - src/ingestion/bronze_match_ids.py
    - src/ingestion/bronze_match_raw.py
    - notebooks/ingest_league_entries.py
    - notebooks/ingest_match_ids.py
    - notebooks/ingest_match_raw.py
  modified: []

key-decisions:
  - "ingestion_log CREATE TABLE placed in ingest_league_entries.py only — first task in DAG; other notebooks append-write assuming table exists"
  - "LEFT ANTI JOIN reads from lol_analytics.bronze.match_ids vs match_raw — avoids wasting API quota on already-ingested matches (D-02)"
  - "MERGE keys: league_entries=(puuid,_region,_tier), match_ids=(puuid,match_id), match_raw=(match_id) — all idempotent"

patterns-established:
  - "Pattern: MERGE INTO lol_analytics.bronze.* using staging temp view — all bronze tables use this pattern"
  - "Pattern: Anti-join pre-check before expensive API loops — reduces quota burn on restarts"
  - "Pattern: RiotRateLimiter() instantiated once per notebook, passed through to all ingest_* functions"

requirements-completed: [BRZ-04, BRZ-05, BRZ-06, BRZ-10]

# Metrics
duration: 3min
completed: 2026-04-13
---

# Phase 02 Plan 03: Bronze Ingestion Chain Summary

**Three bronze ingestion modules with paginated API calls, LEFT ANTI JOIN pre-check, MERGE deduplication, and DAB notebook entry points writing to lol_analytics.bronze.{league_entries,match_ids,match_raw,ingestion_log}**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-13T22:21:48Z
- **Completed:** 2026-04-13T22:24:50Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Implemented the three-step bronze ingestion chain: league_entries (seeds PUUIDs) → match_ids (seeds match ID list) → match_raw (fetches full match JSON)
- Applied LEFT ANTI JOIN pre-check in bronze_match_raw.py so restarts skip already-ingested matches and don't burn API quota
- Created three DAB notebook entry points following smoke_test.py pattern exactly: sys.path defensive insert, RiotRateLimiter() singleton, dbutils.secrets.get, ingestion_log append write

## Task Commits

Each task was committed atomically:

1. **Task 1: ingestion package, league_entries and match_ids modules** - `ef63883` (feat)
2. **Task 2: bronze_match_raw module and three DAB notebook entry points** - `8fc215f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/ingestion/__init__.py` — Package marker
- `src/ingestion/bronze_league_entries.py` — League-Exp-V4 paginated ingest; MERGE on (puuid, _region, _tier); CREATE TABLE lol_analytics.bronze.league_entries USING DELTA
- `src/ingestion/bronze_match_ids.py` — Match-V5 IDs per PUUID from league_entries; MERGE on (puuid, match_id); CREATE TABLE lol_analytics.bronze.match_ids USING DELTA
- `src/ingestion/bronze_match_raw.py` — Match-V5 full detail with LEFT ANTI JOIN pre-check; MERGE on match_id; CREATE TABLE lol_analytics.bronze.match_raw USING DELTA
- `notebooks/ingest_league_entries.py` — DAB entry point; creates ingestion_log with D-06 7-field schema; writes SUCCESS row
- `notebooks/ingest_match_ids.py` — DAB entry point; appends to ingestion_log
- `notebooks/ingest_match_raw.py` — DAB entry point; appends to ingestion_log

## Decisions Made

- ingestion_log CREATE TABLE placed in ingest_league_entries.py only (first DAG task); other notebooks use append mode assuming table exists — avoids race conditions if notebooks run in parallel in the future
- LEFT ANTI JOIN filters against lol_analytics.bronze.match_raw before any API calls, preventing quota waste on repeated runs (D-02 pattern)
- All MERGE statements use WHEN NOT MATCHED THEN INSERT * only — no UPDATE clause needed since raw Bronze stores immutable snapshots

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Local Python environment lacks pyspark — import verification ran structurally via grep checks instead of live import. All done criteria verified against file content. This is expected; these modules only run on Databricks runtime.

## User Setup Required

None — no external service configuration required for this plan. Databricks runtime and UC three-part names are prerequisites already covered by Phase 1.

## Next Phase Readiness

- Bronze ingestion chain complete: league_entries → match_ids → match_raw sequential dependency chain implemented
- Plan 02-04 (match_timeline_raw, summoner_raw, account_raw) can proceed immediately
- Plan 02-05 (DAB job YAML wiring) depends on all ingestion modules being present — now satisfied for plans 03 and 04

---
*Phase: 02-bronze-ingestion-pipeline*
*Completed: 2026-04-13*
