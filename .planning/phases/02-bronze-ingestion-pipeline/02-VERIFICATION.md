---
phase: 02-bronze-ingestion-pipeline
verified: 2026-04-13T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 02: Bronze Ingestion Pipeline Verification Report

**Phase Goal:** Build the complete Bronze ingestion pipeline — Riot API client with rate limiting, platform routing config, 6 Delta table ingestion modules (league_entries, match_ids, match_raw, match_timeline, summoner, account), 6 DAB notebook entry points, DAB ingestion job with 6-task DAG, and unit tests with zero live API calls.
**Verified:** 2026-04-13
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | RiotRateLimiter enforces both buckets simultaneously | VERIFIED | `acquire()` checks `_sec_tokens >= 1 AND _min_tokens >= 1` before returning; both decremented atomically under lock (riot_client.py L75-78) |
| 2 | call_riot_api() reads Retry-After on 429 app/method limits and sleeps exactly that many seconds | VERIFIED | L129-130: `retry_after = int(headers.get("Retry-After", 1)); time.sleep(retry_after)`; test_riot_client.py L157-176 asserts `5 in sleep_durations` |
| 3 | get_region_host('KR') returns 'asia.api.riotgames.com' (NOT 'kr.api.riotgames.com') | VERIFIED | config.py L20-21: `"KR": "asia"`; get_region_host returns `f"{region}.api.riotgames.com"` (L78); test_config.py L135 asserts exact value |
| 4 | All Bronze tables use lol_analytics.bronze.* UC three-part names (no DBFS) | VERIFIED | Every ingestion module uses `lol_analytics.bronze.<table>` in CREATE TABLE, MERGE, and anti-join queries; no DBFS paths found |
| 5 | bronze.summoner_raw uses get_platform_host() (PLATFORM routing) | VERIFIED | bronze_summoner.py L19: `from src.config import get_platform_host`; L40: `platform_host = get_platform_host(region)` |
| 6 | bronze.account_raw uses get_region_host() (REGIONAL routing) | VERIFIED | bronze_account.py L19: `from src.config import get_region_host`; L40: `region_host = get_region_host(region)` |
| 7 | ingestion_job.yml has 6 tasks with correct depends_on DAG | VERIFIED | league_entries (root) → match_ids → match_raw → match_timeline; match_ids → summoner → account; 6 tasks confirmed |
| 8 | 6 ingestion modules exist with MERGE deduplication | VERIFIED | All 6 files present in src/ingestion/; each has MERGE INTO with documented merge key |
| 9 | 6 DAB notebook entry points exist and wire to ingestion modules | VERIFIED | All 6 notebooks present; each imports and calls the corresponding ingest_* function |
| 10 | Unit tests pass locally with zero live API calls | VERIFIED | 55 tests pass (pytest 0.12s); all HTTP via `requests.get` is mocked with `patch` |
| 11 | call_riot_api() raises RiotApiError on 404 (not bare HTTPError) | VERIFIED | riot_client.py L137-138: explicit `raise RiotApiError(404, url)`; test confirms `exc_info.value.status_code == 404` |

**Score: 11/11 truths verified**

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `src/riot_client.py` | VERIFIED | RiotRateLimiter + call_riot_api(); dual-bucket; 429 handling; 142 lines |
| `src/config.py` | VERIFIED | 17-platform PLATFORM_TO_REGION; get_platform_host(); get_region_host(); get_job_params(); 108 lines |
| `src/common/exceptions.py` | VERIFIED | ConfigError, RiotApiError (with status_code + url attrs), RateLimitError |
| `src/common/logger.py` | VERIFIED | get_logger() imported and used across all modules |
| `src/ingestion/bronze_league_entries.py` | VERIFIED | MERGE on (puuid, _region, _tier); pagination until empty page |
| `src/ingestion/bronze_match_ids.py` | VERIFIED | MERGE on (puuid, match_id); reads PUUIDs from league_entries |
| `src/ingestion/bronze_match_raw.py` | VERIFIED | Anti-join pre-check; MERGE on match_id; regional routing |
| `src/ingestion/bronze_match_timeline.py` | VERIFIED | Anti-join pre-check; MERGE on match_id; get_region_host() confirmed |
| `src/ingestion/bronze_summoner.py` | VERIFIED | Anti-join pre-check; MERGE on puuid; get_platform_host() confirmed |
| `src/ingestion/bronze_account.py` | VERIFIED | Anti-join pre-check; MERGE on puuid; get_region_host() confirmed |
| `notebooks/ingest_league_entries.py` | VERIFIED | Full notebook: sys.path setup, get_job_params, RiotRateLimiter, ingest call, ingestion_log write |
| `notebooks/ingest_match_ids.py` | VERIFIED | Wired to bronze_match_ids.ingest_match_ids |
| `notebooks/ingest_match_raw.py` | VERIFIED | Wired to bronze_match_raw.ingest_match_raw |
| `notebooks/ingest_match_timeline.py` | VERIFIED | Wired to bronze_match_timeline.ingest_match_timeline |
| `notebooks/ingest_summoner.py` | VERIFIED | Wired to bronze_summoner.ingest_summoner |
| `notebooks/ingest_account.py` | VERIFIED | Wired to bronze_account.ingest_account |
| `resources/jobs/ingestion_job.yml` | VERIFIED | 6 tasks; git_source; 14400s timeout; KR/CHALLENGER defaults; correct depends_on chain |
| `tests/unit/test_riot_client.py` | VERIFIED | 18 tests; TestRiotRateLimiterInit, TestRiotRateLimiterAcquire, TestCallRiotApi; all mocked |
| `tests/unit/test_config.py` | VERIFIED | 37 tests; all 17 platforms, get_platform_host, get_region_host, get_job_params |
| `tests/conftest.py` | VERIFIED | mock_dbutils, mock_response_200, mock_response_429 fixtures |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| call_riot_api() | RiotRateLimiter.acquire() | called before every requests.get() | WIRED | riot_client.py L116: `limiter.acquire()` precedes L117: `requests.get()` |
| bronze_match_ids | bronze_league_entries (reads PUUIDs) | spark.sql SELECT from lol_analytics.bronze.league_entries | WIRED | bronze_match_ids.py L51-55 |
| bronze_match_raw | bronze_match_ids (anti-join) | LEFT ANTI JOIN lol_analytics.bronze.match_ids | WIRED | bronze_match_raw.py L55-60 |
| bronze_match_timeline | bronze_match_raw (anti-join) | LEFT ANTI JOIN lol_analytics.bronze.match_raw | WIRED | bronze_match_timeline.py L54-59 |
| bronze_summoner | bronze_league_entries (anti-join) | LEFT ANTI JOIN lol_analytics.bronze.league_entries | WIRED | bronze_summoner.py L55-61 |
| bronze_account | bronze_league_entries (anti-join) | LEFT ANTI JOIN lol_analytics.bronze.league_entries | WIRED | bronze_account.py L55-61 |
| ingestion_job.yml | notebooks/ingest_* | notebook_path + source: GIT | WIRED | All 6 notebook_path entries use source: GIT |
| test_riot_client.py | src/riot_client.py | direct import + patch("requests.get") | WIRED | All HTTP calls patched; no live requests |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces ingestion modules (data producers), not components that render dynamic data. The data flow is outward: API → Delta tables.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 55 unit tests pass locally | `pytest tests/unit/ -x -q` (via mls venv) | 55 passed in 0.12s | PASS |
| get_region_host('KR') returns asia host | Code read at config.py L20-21, L73-79 | `PLATFORM_TO_REGION["KR"] = "asia"` → returns `"asia.api.riotgames.com"` | PASS |
| ingestion_job.yml validates 6 tasks | Count of `task_key:` in YAML | 6 task_key entries confirmed | PASS |
| No live API calls in tests | grep for unpatched requests.get in tests/ | All `requests.get` calls are inside `patch("requests.get", ...)` context managers | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| BRZ-01 | 02-01 | Dual-bucket rate limiter (20/sec + 100/2min) + Retry-After parsing | SATISFIED | riot_client.py RiotRateLimiter; call_riot_api() 429 handling |
| BRZ-02 | 02-02 | region/tier are DAB job parameters, never hardcoded | SATISFIED | ingestion_job.yml parameters block; notebooks read via get_job_params(dbutils); no hardcoded KR/CHALLENGER in ingestion code |
| BRZ-03 | 02-02 | 17-platform PLATFORM_TO_REGION config | SATISFIED | config.py L19-41: all 17 platforms present; test_config.py verifies count == 17 |
| BRZ-04 | 02-03 | bronze.league_entries from League-Exp-V4, paginated | SATISFIED | bronze_league_entries.py: pagination loop, MERGE on (puuid, _region, _tier) |
| BRZ-05 | 02-03 | bronze.match_ids from Match-V5, MERGE dedup on (puuid, match_id) | SATISFIED | bronze_match_ids.py: MERGE ON target.puuid = source.puuid AND target.match_id = source.match_id |
| BRZ-06 | 02-03 | bronze.match_raw from Match-V5, MERGE dedup on match_id | SATISFIED | bronze_match_raw.py: anti-join + MERGE ON target.match_id = source.match_id |
| BRZ-07 | 02-04 | bronze.match_timeline_raw, separate DAB task | SATISFIED | bronze_match_timeline.py + match_timeline_task in ingestion_job.yml as independent task |
| BRZ-08 | 02-04 | bronze.summoner_raw via Summoner-V4 by PUUID | SATISFIED | bronze_summoner.py: PLATFORM routing, anti-join, MERGE on puuid |
| BRZ-09 | 02-04 | bronze.account_raw via Account-V1 by PUUID | SATISFIED | bronze_account.py: REGIONAL routing, anti-join, MERGE on puuid |
| BRZ-10 | 02-03 | All Bronze tables: Delta format, UC three-part names, no DBFS | SATISFIED | Every table: `USING DELTA` + `lol_analytics.bronze.*`; no dbfs: paths found anywhere |
| TEST-02 | 02-05 | Unit tests for RiotApiClient rate limiter (mocked HTTP) | SATISFIED | test_riot_client.py: 18 tests, all mocked; 55 total pass |
| TEST-04 | 02-05 | pytest runs locally without live Databricks cluster | SATISFIED | 55 passed in 0.12s with no Spark/cluster dependency; pytest.ini configures pythonpath=. |

**Note:** BRZ-10 was listed in plan 02-03 requirements but not in the prompt's phase requirement IDs (BRZ-01 through BRZ-09, TEST-02, TEST-04). It is fully implemented and satisfied — all tables use DELTA + UC three-part names.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/unit/test_placeholder.py` | 7 | `def test_placeholder(): assert True` | Info | Phase 1 artifact; not removed in Phase 2. Does not block any functionality — pytest collects it as a passing test. No goal impact. |
| `resources/jobs/ingestion_job.yml` | 2 | Comment: "Replaces the Phase 1 placeholder" | Info | Documentation comment only; no functional impact. |

No blockers or warnings found.

---

### Human Verification Required

#### 1. DAB Bundle Validate

**Test:** Run `databricks bundle validate` from repo root with valid Databricks CLI auth configured.
**Expected:** Bundle validates without errors; ingestion_job resolves 6 tasks with correct notebook paths.
**Why human:** Requires live Databricks CLI credentials and workspace connectivity.

#### 2. End-to-End Ingestion Run (KR/CHALLENGER)

**Test:** Trigger `dbx-mls-ingestion` job in Databricks workspace with region=KR, tier=CHALLENGER.
**Expected:** All 6 tasks complete; `lol_analytics.bronze.league_entries` contains rows; anti-joins in subsequent tasks skip already-ingested rows on re-run.
**Why human:** Requires live Riot API key, Databricks workspace, Unity Catalog lol_analytics catalog.

#### 3. Rate Limiter Behavior Under Sustained Load

**Test:** Observe `X-App-Rate-Limit-Count` log output during a real ingestion run.
**Expected:** Count never exceeds `20:1` (per-second bucket) or `100:120` (2-minute bucket); no unexpected 429s from rate limiter failure.
**Why human:** Token bucket correctness under real timing conditions can only be confirmed with live API traffic.

---

### Gaps Summary

No gaps. All 11 observable truths verified against actual code. All 12 requirement IDs (BRZ-01 through BRZ-10, TEST-02, TEST-04) are satisfied with concrete implementation evidence. All 20 required artifacts exist, are substantive (not stubs), and are wired into the pipeline. The 55-test suite passes locally in 0.12 seconds with zero live API calls.

The only items routing to human verification are operational concerns (live cluster, live API key) that cannot be verified programmatically — they do not represent gaps in the implementation.

---

_Verified: 2026-04-13_
_Verifier: Claude (gsd-verifier)_
