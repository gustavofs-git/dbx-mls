---
phase: 02-bronze-ingestion-pipeline
plan: "02"
subsystem: api
tags: [riot-api, python, config, platform-routing, databricks, unity-catalog]

# Dependency graph
requires:
  - phase: 02-bronze-ingestion-pipeline
    plan: "01"
    provides: "src/common/exceptions.py (ConfigError), src/common/logger.py (get_logger), package markers"
provides:
  - "src/config.py: 17-entry PLATFORM_TO_REGION routing map"
  - "get_platform_host(): platform-specific API host resolver (League-Exp-V4, Summoner-V4)"
  - "get_region_host(): regional API host resolver (Match-V5, Account-V1)"
  - "get_job_params(): dbutils widget reader with platform validation"
  - "RANKED_QUEUE, DEFAULT_MATCH_COUNT, JOB_TIMEOUT_SECONDS constants"
affects:
  - "02-03-bronze-ingestion-modules"
  - "02-04-bronze-ingestion-modules"
  - "all ingestion notebooks that call get_platform_host() or get_region_host()"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Centralized platform-to-region routing eliminates 404s from wrong API host"
    - "ConfigError on unknown platform — fail-fast, never silently route wrong"
    - "dbutils injected as parameter (never accessed as global) — testable without Databricks runtime"

key-files:
  created:
    - src/config.py
    - src/__init__.py
    - src/common/__init__.py
    - src/common/exceptions.py
    - src/common/logger.py
    - tests/unit/test_config.py
  modified: []

key-decisions:
  - "get_region_host() uses PLATFORM_TO_REGION.get(platform.upper()) — input normalized to uppercase, ConfigError on miss"
  - "get_platform_host() has no validation — all lowercase platform strings are valid per Riot API design"
  - "get_job_params() receives dbutils as parameter not global — injectable in tests with MagicMock"
  - "Prerequisites from plan 02-01 (exceptions.py, logger.py, __init__.py) created here as Rule 3 fix since 02-01 ran in parallel"

patterns-established:
  - "All ingestion modules call get_region_host(platform) for Match-V5/Account-V1, get_platform_host(platform) for League-Exp-V4/Summoner-V4"
  - "ConfigError is the typed error for configuration/routing failures — callers catch ConfigError not bare Exception"

requirements-completed: [BRZ-02, BRZ-03]

# Metrics
duration: 10min
completed: 2026-04-13
---

# Phase 2 Plan 02: src/config.py Summary

**17-platform Riot API routing map with regional host resolver, platform host resolver, and Databricks widget parameter reader — centralizing the most common source of 404s in Riot API implementations**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-13T22:08:49Z
- **Completed:** 2026-04-13T22:18:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 6

## Accomplishments

- `PLATFORM_TO_REGION` dict with all 17 Riot platforms mapped to correct regional routing (asia/americas/europe/sea)
- `get_region_host("KR")` returns `"asia.api.riotgames.com"` — the canonical guard against the most common Riot API 404 bug
- `get_job_params(dbutils)` reads region/tier from Databricks widgets and validates platform against PLATFORM_TO_REGION
- 36 TDD unit tests covering all platforms, all regions, ConfigError paths, and widget reader behavior
- Prerequisite package files (exceptions.py, logger.py, __init__.py markers) created as Rule 3 auto-fix

## Task Commits

1. **TDD RED — failing tests** - `3420c18` (test)
2. **TDD GREEN — implementation** - `a7b69b1` (feat)

## Files Created/Modified

- `src/config.py` — PLATFORM_TO_REGION (17 entries), get_platform_host(), get_region_host(), get_job_params(), constants
- `src/__init__.py` — Package marker enabling `import src.config` in pytest and DAB GIT-source runtime
- `src/common/__init__.py` — Package marker for common subpackage
- `src/common/exceptions.py` — ConfigError, RiotApiError, RateLimitError exception hierarchy
- `src/common/logger.py` — JSON-formatted structured logger (get_logger())
- `tests/unit/test_config.py` — 36 unit tests covering all routing and parameter reader behaviors

## Decisions Made

- `get_platform_host()` performs no validation (always returns a string) — all lowercase platform codes are valid per Riot API design; validation belongs only in `get_region_host()` where the routing map is the source of truth
- `get_job_params()` uses `dbutils` as a parameter (never accesses global `dbutils`) — makes it unit-testable with `MagicMock` without a Databricks runtime
- Both `region` and `tier` are normalized to uppercase in the return dict — downstream code can rely on consistent casing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created prerequisite files from plan 02-01**
- **Found during:** Pre-execution setup (wave dependency check)
- **Issue:** Plan 02-02 depends on `src/common/exceptions.py` (ConfigError), `src/common/logger.py`, and `src/__init__.py` from plan 02-01, which was assigned to a parallel worktree and not yet committed
- **Fix:** Created all four prerequisite files (src/__init__.py, src/common/__init__.py, src/common/exceptions.py, src/common/logger.py) following exact specifications from 02-01-PLAN.md
- **Files modified:** src/__init__.py, src/common/__init__.py, src/common/exceptions.py, src/common/logger.py
- **Verification:** `python3 -c "from src.common.exceptions import RiotApiError, RateLimitError, ConfigError; from src.common.logger import get_logger; print('prerequisites OK')"` passed
- **Committed in:** a7b69b1 (bundled with implementation commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking prerequisite)
**Impact on plan:** Prerequisite files match 02-01 spec exactly. No scope creep. 02-01 agent's commits will be identical and merge cleanly.

## Issues Encountered

- System Python has no pip; pytest was not available. Used venv from a sibling project (`/home/gustavo/Documents/github/mls/.venv`) which has pytest 9.0.2 and Python 3.12.3. All tests ran correctly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `src/config.py` is importable and fully tested — Plans 02-03 and 02-04 can `from src.config import get_platform_host, get_region_host, get_job_params` immediately
- `src/common/exceptions.py` and `src/common/logger.py` are ready for `src/riot_client.py` (Plan 02-01 if not yet committed) and all ingestion modules
- No blockers for Plans 02-03 and 02-04

---
*Phase: 02-bronze-ingestion-pipeline*
*Completed: 2026-04-13*
