---
phase: 02-bronze-ingestion-pipeline
plan: "01"
subsystem: api
tags: [riot-api, rate-limiter, token-bucket, requests, logging, exceptions, tdd]

# Dependency graph
requires: []
provides:
  - RiotRateLimiter class (dual-bucket token bucket, 20 req/sec + 100 req/2min)
  - call_riot_api() function with 429 handling and Retry-After parsing
  - src/common/exceptions.py: RiotApiError, RateLimitError, ConfigError
  - src/common/logger.py: get_logger() JSON-formatted structured logger
  - src/__init__.py and src/common/__init__.py package markers
affects:
  - 02-02-bronze-config (imports src.common.exceptions.ConfigError)
  - 02-03-bronze-ingestion (imports RiotRateLimiter, call_riot_api)
  - 02-04-bronze-ingestion (imports RiotRateLimiter, call_riot_api)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-bucket token bucket rate limiter using time.monotonic() for Riot API 20/sec + 100/2min"
    - "call_riot_api() receives limiter as parameter — never instantiated internally"
    - "X-Rate-Limit-Type header distinguishes application/method (Retry-After) from service (backoff+jitter)"
    - "JSON-structured logging via _JsonFormatter for all src/ modules"
    - "TDD: RED commit (failing tests) then GREEN commit (implementation) per plan"

key-files:
  created:
    - src/riot_client.py
    - src/common/exceptions.py
    - src/common/logger.py
    - src/__init__.py
    - src/common/__init__.py
    - tests/unit/test_riot_client.py
  modified: []

key-decisions:
  - "time.sleep(0.05) in acquire() is lock-release wait between bucket checks only — NOT the primary throttle (token bucket IS the throttle)"
  - "RiotRateLimiter instantiated once in driver; passed to call_riot_api() as parameter per D-01"
  - "404 raises RiotApiError(404, url) explicitly before raise_for_status() — downstream can catch 404 vs generic HTTP errors"
  - "pytest venv created at /tmp/dbx-mls-test-venv since no project venv existed; tests run via PYTHONPATH"

patterns-established:
  - "Pattern 1: Dual-bucket token bucket — acquire() checks both sec and min buckets atomically under lock"
  - "Pattern 2: 429 handling — X-Rate-Limit-Type header gates Retry-After vs backoff path"
  - "Pattern 3: get_logger(name) idempotent — no duplicate handlers on repeated calls"

requirements-completed: [BRZ-01]

# Metrics
duration: 3min
completed: 2026-04-13
---

# Phase 02 Plan 01: Riot API Client Core Summary

**Thread-safe dual-bucket token bucket rate limiter (20 req/sec + 100 req/2min) with Retry-After-aware 429 handling in src/riot_client.py, plus JSON logger and typed exception hierarchy**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-13T22:14:56Z
- **Completed:** 2026-04-13T22:18:10Z
- **Tasks:** 2 (Task 1: package markers + helpers; Task 2: riot_client.py with TDD)
- **Files modified:** 6

## Accomplishments

- Created `src/riot_client.py` with `RiotRateLimiter` (dual-bucket token bucket) and `call_riot_api()` with full 429 handling
- Created `src/common/exceptions.py` with `RiotApiError`, `RateLimitError`, `ConfigError` typed hierarchy
- Created `src/common/logger.py` with JSON-formatted `get_logger()` using `_JsonFormatter`
- Created empty `src/__init__.py` and `src/common/__init__.py` package markers for pytest/DAB GIT-source imports
- 18 unit tests written TDD-style (RED then GREEN): rate limiter init, acquire() token consumption/blocking, call_riot_api() 200/404/429 scenarios, header logging

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/ package markers and common helpers** - `6291715` (feat)
2. **Task 2 RED: Failing tests for RiotRateLimiter and call_riot_api** - `8715679` (test)
3. **Task 2 GREEN: Implement RiotRateLimiter and call_riot_api** - `1940b83` (feat)

_Note: TDD task has two commits per TDD protocol (test RED then implementation GREEN)_

## Files Created/Modified

- `src/riot_client.py` — `RiotRateLimiter` class and `call_riot_api()` function; main deliverable
- `src/common/exceptions.py` — `RiotApiError(status_code, url)`, `RateLimitError`, `ConfigError`
- `src/common/logger.py` — `get_logger(name)` returning JSON-formatted `logging.Logger`
- `src/__init__.py` — empty package marker
- `src/common/__init__.py` — empty package marker
- `tests/unit/test_riot_client.py` — 18 unit tests covering rate limiter and API client behavior

## Decisions Made

- `time.sleep(0.05)` in `acquire()` is explicitly the lock-release wait between bucket-check loop iterations, NOT the primary throttle. The token bucket algorithm IS the throttle. Comment and docstring make this explicit per plan constraint.
- `RiotRateLimiter` is instantiated once per driver process and passed into `call_riot_api()` as a parameter. This enforces the D-01 driver-side loop pattern and prevents limiter state reset between calls.
- 404 is caught explicitly before `raise_for_status()` to raise `RiotApiError(404, url)` instead of bare `HTTPError` — downstream ingestion modules can catch 404 specifically for "summoner not found" paths.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- No project virtual environment existed. Created `/tmp/dbx-mls-test-venv` with `requests`, `pytest`, `pytest-mock` installed to run unit tests. Tests ran via `PYTHONPATH=<worktree-root>`. The project's `requirements-dev.txt` specifies the correct packages; this is an environment setup gap, not a code issue.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `src/riot_client.py` fully tested and importable as `from src.riot_client import RiotRateLimiter, call_riot_api`
- Plan 02-02 (config.py) can now import `ConfigError` from `src.common.exceptions`
- Plans 02-03 and 02-04 (ingestion notebooks) can import `RiotRateLimiter` and `call_riot_api` directly
- No blockers; all exports verified importable

---
*Phase: 02-bronze-ingestion-pipeline*
*Completed: 2026-04-13*
