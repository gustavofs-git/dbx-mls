---
phase: "02-bronze-ingestion-pipeline"
plan: "04"
subsystem: "bronze-ingestion"
tags: ["bronze", "ingestion", "match-timeline", "summoner", "account", "routing", "anti-join"]
dependency_graph:
  requires:
    - "02-01"  # riot_client.py, RiotRateLimiter, call_riot_api
    - "02-02"  # config.py, get_platform_host, get_region_host, get_job_params
    - "02-03"  # bronze_match_raw.py (anti-join source for timeline)
  provides:
    - "src/ingestion/bronze_match_timeline.py"
    - "src/ingestion/bronze_summoner.py"
    - "src/ingestion/bronze_account.py"
    - "notebooks/ingest_match_timeline.py"
    - "notebooks/ingest_summoner.py"
    - "notebooks/ingest_account.py"
  affects:
    - "02-05"  # DAB job wiring will include these new notebooks
tech_stack:
  added: []
  patterns:
    - "LEFT ANTI JOIN pre-check before API calls (dedup/idempotency)"
    - "MERGE INTO on natural key (match_id, puuid)"
    - "PLATFORM vs REGIONAL host routing distinction"
    - "ingestion_log append for observability"
key_files:
  created:
    - src/ingestion/bronze_match_timeline.py
    - src/ingestion/bronze_summoner.py
    - src/ingestion/bronze_account.py
    - notebooks/ingest_match_timeline.py
    - notebooks/ingest_summoner.py
    - notebooks/ingest_account.py
  modified: []
decisions:
  - "Match-V5 timeline uses REGIONAL host (asia.api.riotgames.com for KR) — same rule as match detail"
  - "Summoner-V4 uses PLATFORM host (kr.api.riotgames.com for KR) — different from Match-V5/Account-V1"
  - "Account-V1 uses REGIONAL host (asia.api.riotgames.com for KR) — same rule as Match-V5"
  - "Timeline anti-join sources from match_raw (not match_ids) — only fetch timelines for fully-ingested matches"
  - "ingest_match_timeline does not take tier param — timelines are match-scoped, not tier-scoped"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-13"
  tasks_completed: 2
  files_created: 6
  files_modified: 0
---

# Phase 02 Plan 04: Enrichment Ingestion Modules Summary

Three enrichment ingestion modules (match timeline, summoner profiles, account details) with correct Riot API routing and LEFT ANTI JOIN dedup, completing the 6-table Bronze layer.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create three enrichment ingestion modules | 5bab42a | src/ingestion/bronze_match_timeline.py, bronze_summoner.py, bronze_account.py |
| 2 | Create three enrichment DAB notebook entry points | d35f73f | notebooks/ingest_match_timeline.py, ingest_summoner.py, ingest_account.py |

## What Was Built

**Three ingestion modules in `src/ingestion/`:**

- `bronze_match_timeline.py` — fetches Match-V5 `/timeline` endpoint. Anti-join against `match_raw` (only fetch timelines for matches already fully ingested). REGIONAL host. MERGE key: `match_id`.
- `bronze_summoner.py` — fetches Summoner-V4 by PUUID. Anti-join against `league_entries`. PLATFORM host (`kr.api.riotgames.com` for KR). MERGE key: `puuid`.
- `bronze_account.py` — fetches Account-V1 by PUUID. Anti-join against `league_entries`. REGIONAL host (`asia.api.riotgames.com` for KR). MERGE key: `puuid`.

**Three DAB notebook entry points in `notebooks/`:**

- `ingest_match_timeline.py` — region-only (no tier), calls `ingest_match_timeline()`.
- `ingest_summoner.py` — region + tier, calls `ingest_summoner()`.
- `ingest_account.py` — region + tier, calls `ingest_account()`.

All six notebooks write run metadata to `lol_analytics.bronze.ingestion_log` on completion.

## Routing Decision (Critical)

| Module | API | Routing Function | Host (KR) |
|--------|-----|-----------------|-----------|
| bronze_match_timeline.py | Match-V5 timeline | `get_region_host()` | asia.api.riotgames.com |
| bronze_summoner.py | Summoner-V4 | `get_platform_host()` | kr.api.riotgames.com |
| bronze_account.py | Account-V1 | `get_region_host()` | asia.api.riotgames.com |

Using platform host for Account-V1 or Summoner-V4 with regional host produces silent 404s — the routing is enforced at the import level (each module imports only the correct function).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all modules are fully wired with correct routing, anti-join logic, and MERGE patterns.

## Self-Check: PASSED

- `src/ingestion/bronze_match_timeline.py` — exists, correct routing (`get_region_host`), LEFT ANTI JOIN, MERGE on `match_id`
- `src/ingestion/bronze_summoner.py` — exists, correct routing (`get_platform_host`), LEFT ANTI JOIN, MERGE on `puuid`
- `src/ingestion/bronze_account.py` — exists, correct routing (`get_region_host`), LEFT ANTI JOIN, MERGE on `puuid`
- `notebooks/ingest_match_timeline.py` — exists, no tier param, RiotRateLimiter(), ingestion_log write
- `notebooks/ingest_summoner.py` — exists, tier param present, RiotRateLimiter(), ingestion_log write
- `notebooks/ingest_account.py` — exists, tier param present, RiotRateLimiter(), ingestion_log write
- Commit 5bab42a — verified in git log
- Commit d35f73f — verified in git log
- 6 total ingest_*.py notebooks in notebooks/
