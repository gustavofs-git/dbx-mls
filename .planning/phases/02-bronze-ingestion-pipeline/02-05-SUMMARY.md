---
phase: 02-bronze-ingestion-pipeline
plan: "05"
subsystem: testing
tags: [pytest, databricks, dabs, ingestion-job, rate-limiter, config, unit-tests]

# Dependency graph
requires:
  - phase: 02-bronze-ingestion-pipeline-01
    provides: src/riot_client.py — RiotRateLimiter and call_riot_api() to test against
  - phase: 02-bronze-ingestion-pipeline-02
    provides: src/config.py — PLATFORM_TO_REGION, get_region_host(), get_job_params() to test against
provides:
  - tests/__init__.py and tests/unit/__init__.py — package markers for pytest collection
  - tests/conftest.py — shared fixtures (mock_dbutils, mock_response_200, mock_response_429)
  - pytest.ini with pythonpath = . — enables src/ imports without pip install
  - resources/jobs/ingestion_job.yml — full 6-task DAB ingestion job replacing placeholder
affects:
  - phase-03-silver (ingestion_job.yml is the deploy target that must pass bundle validate)
  - ci-cd (pytest tests/unit/ in CI already covers the new tests — no ci.yml changes needed)

# Tech tracking
tech-stack:
  added: [pytest-mock conftest fixtures, DAB job YAML with git_source and depends_on chains]
  patterns:
    - pytest pythonpath=. in pytest.ini for zero-install src/ imports
    - conftest.py shared fixtures for HTTP mock factories
    - DAB ingestion_job with git_source.git_branch=main and source=GIT on all notebook tasks
    - Parallel DAG chains: match_ids → summoner → account runs parallel to match_raw → timeline

key-files:
  created:
    - tests/__init__.py
    - tests/unit/__init__.py
    - tests/conftest.py
    - resources/jobs/ingestion_job.yml (replaced placeholder)
  modified:
    - pytest.ini (added pythonpath = .)

key-decisions:
  - "pytest.ini requires pythonpath=. for src/ imports without pip install — added as Rule 3 auto-fix"
  - "summoner_task depends on match_ids_task (not match_raw_task) — runs parallel to timeline chain"
  - "test files from prior plans (02-01, 02-02) are complete and used as-is — not recreated"
  - "ingestion_job.yml uses timeout_seconds=14400 (4h) — cold KR Challenger run is 2-3.5h"

patterns-established:
  - "Pattern: source=GIT on all DAB notebook tasks — SP file access restriction workaround"
  - "Pattern: data_security_mode=SINGLE_USER on all job clusters — UC workspace requirement"
  - "Pattern: singleNode profile (not singleUser — singleUser is a UC access mode, not cluster profile)"

requirements-completed: [TEST-02, TEST-04]

# Metrics
duration: 25min
completed: 2026-04-13
---

# Phase 02 Plan 05: Wire-up — Job DAG, Unit Tests, Test Scaffolding Summary

**Full DAB ingestion job with 6-task DAG wired (league→match_ids→match_raw→timeline parallel with match_ids→summoner→account), Wave-0 pytest scaffolding, 55 unit tests passing with zero live API calls**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-13T00:00:00Z
- **Completed:** 2026-04-13T00:25:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Replaced `resources/jobs/ingestion_job.yml` placeholder with a full 6-task DAB job using `source: GIT`, `data_security_mode: SINGLE_USER`, `timeout_seconds: 14400`, and runtime parameters for region/tier
- Created `tests/__init__.py`, `tests/unit/__init__.py`, and `tests/conftest.py` — Wave-0 package markers and shared HTTP mock fixtures
- Added `pythonpath = .` to `pytest.ini` as an auto-fix so `src/` is importable without a local pip install
- All 55 unit tests pass (test_riot_client.py + test_config.py + test_placeholder.py) with zero live API calls

## Task Commits

1. **Task 1: Wave-0 test scaffolding, package markers, conftest, pytest pythonpath** - `07a6431` (feat)
2. **Task 2: Full 6-task DAB ingestion job replacing placeholder** - `470a8bc` (feat)

**Plan metadata:** `{docs-hash}` (docs: complete plan)

## Files Created/Modified
- `tests/__init__.py` — empty package marker
- `tests/unit/__init__.py` — empty package marker
- `tests/conftest.py` — shared fixtures: mock_dbutils, mock_response_200, mock_response_429
- `pytest.ini` — added `pythonpath = .` (Rule 3 auto-fix for src/ import resolution)
- `resources/jobs/ingestion_job.yml` — full 6-task DAB ingestion job (replaced `jobs: {}` placeholder)

## Decisions Made
- `summoner_task` depends on `match_ids_task` (not `match_raw_task`) — allows summoner/account enrichment chain to run in parallel with the match_timeline chain, reducing total wall-clock time
- Test files from 02-01 and 02-02 agents (`test_riot_client.py`, `test_config.py`) were complete and used as-is — no recreation needed
- `ingestion_job.yml` uses `git_source.git_branch: main` pointing to public GitHub — consistent with Phase 1 SP file access restriction pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `pythonpath = .` to pytest.ini**
- **Found during:** Task 1 (Wave-0 test scaffolding verification)
- **Issue:** `pytest tests/unit/` failed with `ModuleNotFoundError: No module named 'src'` — pytest.ini had no PYTHONPATH configuration
- **Fix:** Added `pythonpath = .` to `pytest.ini` so the project root is on sys.path at test time
- **Files modified:** `pytest.ini`
- **Verification:** All 55 tests pass after the fix; `from src.riot_client import ...` resolves correctly
- **Committed in:** `07a6431` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — missing pythonpath config)
**Impact on plan:** Fix required for any test to run locally. No scope creep. CI already works because it installs the package before running pytest.

## Issues Encountered
- Prior plan worktree did not include src/ files at merge time — fast-forward merge of commit `5266c0e` brought in all Phase 02 plan 01–04 outputs before execution began

## User Setup Required

Java 11 must be installed before `make test` if running PySpark tests locally:

```bash
sudo apt-get install openjdk-11-jdk
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
```

See `docs/setup.md` section "4. Local Dev Environment → Java 11" for full instructions.

Note: The current tests in `test_riot_client.py` and `test_config.py` do NOT require PySpark/Java — they use pure Python mocks. Java 11 is only needed if PySpark-based ingestion tests are added in Phase 3.

## Next Phase Readiness
- ingestion_job.yml is deployable once `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID` are set in GitHub Actions secrets — Phase 2 is ready to deploy
- All TEST-02 and TEST-04 requirements satisfied — unit tests for rate limiter and config are in place
- Phase 03 (Silver transformation) can begin — Bronze ingestion pipeline is fully defined and testable

---
*Phase: 02-bronze-ingestion-pipeline*
*Completed: 2026-04-13*
