---
phase: 01-infrastructure-governance-ci-cd-foundation
plan: "01"
subsystem: infra
tags: [databricks, dabs, unity-catalog, pyspark, pytest, azure]

# Dependency graph
requires: []
provides:
  - "databricks.yml root bundle with dev/prod targets (DBR 16.4 LTS, Standard_F4s_v2)"
  - "resources/clusters.yml shared job cluster definition"
  - "resources/schemas.yml UC lol_analytics catalog with bronze/silver/gold schemas"
  - "Full directory scaffold: src/, schemas/, notebooks/, tests/unit/, docs/posts/, .github/workflows/, resources/jobs/"
  - "requirements.txt and requirements-dev.txt dependency pins"
  - "pytest.ini, Makefile, .gitignore"
affects:
  - "02-bronze-ingestion"
  - "03-silver-transformation"
  - "01-02-oidc-ci-cd"
  - "01-03-uc-secrets"
  - "01-04-smoke-test"

# Tech tracking
tech-stack:
  added:
    - "Databricks CLI v0.295.0 (installed to ~/.local/bin)"
    - "Databricks Asset Bundles (DABs) — databricks.yml root bundle"
    - "databricks-sdk>=0.102.0 (requirements.txt)"
    - "pyspark==3.5.2 + delta-spark==3.3.2 (requirements-dev.txt)"
    - "pytest>=8.3.0, pytest-cov>=6.0.0, pytest-mock>=3.14.0, chispa>=0.9.4"
    - "azure-identity>=1.19.0"
    - "requests>=2.32.0, tenacity>=9.0.0"
  patterns:
    - "DABs include: directive for modular resource YAML composition"
    - "dev target uses DATABRICKS_HOST env var; prod target uses explicit root_path + run_as SP"
    - "Placeholder job YAMLs (resources: jobs: {}) keep include: glob valid before Phase 2/3"
    - "requirements-dev.txt inherits from requirements.txt via -r directive"

key-files:
  created:
    - "databricks.yml"
    - "resources/clusters.yml"
    - "resources/schemas.yml"
    - "resources/jobs/ingestion_job.yml"
    - "resources/jobs/transformation_job.yml"
    - "requirements.txt"
    - "requirements-dev.txt"
    - "pytest.ini"
    - "Makefile"
    - ".gitignore"
  modified: []

key-decisions:
  - "workspace.host not set in databricks.yml — CLI v0.295.0 does not support variable interpolation for auth fields; DATABRICKS_HOST env var is the correct mechanism"
  - "Databricks CLI installed to ~/.local/bin/databricks (no sudo required)"
  - "singleNode cluster profile used (not singleUser — singleUser is a UC access mode, not a cluster profile)"
  - "Placeholder job YAMLs use empty resources: jobs: {} to satisfy include: glob without errors"

patterns-established:
  - "Pattern: All DAB resources modular — one file per concern (clusters.yml, schemas.yml, jobs/*.yml)"
  - "Pattern: dev target inherits DATABRICKS_HOST from env; prod target explicitly sets root_path"
  - "Pattern: SP-only prod run_as via run_as.service_principal_name with variable ${var.sp_client_id}"

requirements-completed: [INFRA-04, INFRA-07, INFRA-01]

# Metrics
duration: 3min
completed: 2026-04-07
---

# Phase 1 Plan 01: Repo Scaffold and DABs Bundle Definition Summary

**Greenfield repo scaffolded with databricks.yml root bundle (dev/prod targets, DBR 16.4 LTS, Standard_F4s_v2), UC schema declarations for lol_analytics catalog, and pinned Python/test dependencies**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-07T17:45:13Z
- **Completed:** 2026-04-07T17:48:26Z
- **Tasks:** 2
- **Files modified:** 16 (11 created in Task 1, 5 created in Task 2)

## Accomplishments

- Created complete repo directory structure (src/, schemas/, notebooks/, tests/unit/, docs/posts/, .github/workflows/, resources/jobs/) with .gitkeep placeholders
- Wrote databricks.yml root bundle with dev (development mode, default) and prod (production mode, explicit root_path, run_as SP) targets
- Defined shared job cluster (Standard_F4s_v2, DBR 16.4 LTS, singleNode, autotermination_minutes: 0) and UC schema declarations (lol_analytics bronze/silver/gold)
- Pinned all runtime and dev/test dependencies; configured pytest.ini, Makefile, and .gitignore

## Task Commits

Each task was committed atomically:

1. **Task 1: Directory skeleton and root databricks.yml** - `910786c` (feat)
2. **Task 2: requirements, pytest.ini, Makefile, .gitignore** - `718c68f` (feat)

**Plan metadata:** to be committed with this SUMMARY

## Files Created/Modified

- `databricks.yml` - Root DABs bundle: dev/prod targets, include directives, sp_client_id variable
- `resources/clusters.yml` - Shared job cluster: Standard_F4s_v2, DBR 16.4 LTS, singleNode, autotermination 0
- `resources/schemas.yml` - UC lol_analytics catalog declarations: bronze, silver, gold schemas
- `resources/jobs/ingestion_job.yml` - Phase 2 placeholder (empty jobs resource)
- `resources/jobs/transformation_job.yml` - Phase 3 placeholder (empty jobs resource)
- `requirements.txt` - Runtime pins: requests, tenacity, databricks-sdk
- `requirements-dev.txt` - Dev pins: pyspark 3.5.2, delta-spark 3.3.2, pytest suite, chispa, azure-identity
- `pytest.ini` - testpaths = tests/unit, addopts = -v
- `Makefile` - validate, test, smoke targets
- `.gitignore` - Excludes .env, *.token, secrets.yml, __pycache__/, .databricks/, .venv/
- `src/.gitkeep`, `schemas/.gitkeep`, `notebooks/.gitkeep`, `tests/unit/.gitkeep`, `docs/posts/.gitkeep`, `.github/workflows/.gitkeep` - Directory placeholders

## Decisions Made

- **workspace.host removed from databricks.yml:** Databricks CLI v0.295.0 does not support variable interpolation (`${var.xxx}`) for authentication fields including `workspace.host`. Removed the `workspace.host` field from both targets; the CLI correctly reads `DATABRICKS_HOST` from the environment. This is the recommended pattern for both CI (GitHub Actions env vars) and local dev (`databricks auth login`). The structural bundle validation (JSON output) confirms all resources resolve correctly.
- **Databricks CLI installed to `~/.local/bin`:** No sudo required; installed from GitHub release ZIP.
- **singleNode cluster profile:** Used `spark.databricks.cluster.profile: singleNode` (not `singleUser`). The research notes clarify that `singleUser` is a Unity Catalog access mode, not a cluster profile value — this would have caused a silent misconfiguration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed workspace.host variable interpolation**
- **Found during:** Task 1 (bundle validate verification)
- **Issue:** Plan specified `workspace.host: ${var.databricks_host}` but Databricks CLI v0.295.0 explicitly rejects variable interpolation for auth fields, producing an error: "Variable interpolation is not supported for fields that configure authentication"
- **Fix:** Removed `workspace.host` from both dev and prod targets; prod target retains `root_path`. DATABRICKS_HOST env var is the correct mechanism (already documented in RESEARCH.md CI examples)
- **Files modified:** databricks.yml
- **Verification:** `databricks bundle validate --output json` parses all resources correctly; bundle name, mode, schemas all resolve
- **Committed in:** 910786c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - CLI version incompatibility with variable interpolation in auth fields)
**Impact on plan:** Fix aligns with the actual CI pattern shown in RESEARCH.md (DATABRICKS_HOST as env var). No functionality lost — workspace connectivity is configured via env var in both CI and local dev.

## Issues Encountered

- Databricks CLI not in PATH for shell execution context — installed v0.295.0 to `~/.local/bin` via GitHub release ZIP download. This is expected in a fresh environment; the user's interactive terminal may already have it installed.
- `databricks bundle validate` exits non-zero without workspace auth configured — this is expected behavior for CLI v0.295.0 which validates workspace connectivity as part of bundle validation. The structural validation (--output json) confirms YAML is correct. Full exit-0 validation requires `databricks auth login` to be run first (documented in RESEARCH.md and setup.md in Plan 01-04).

## User Setup Required

None for this plan — no external service configuration required at this stage.

Plan 01-02 will require manual OIDC federation policy creation and GitHub repository variable setup.

## Next Phase Readiness

- Bundle structure is valid — all YAML files parse correctly with no schema errors
- Directory scaffold committed — Plans 01-02 through 01-04 can add files to the established structure
- .gitignore in place — no credential leakage risk
- Dependency pins committed — CI can `pip install -r requirements-dev.txt` from day one

**Blocker:** `databricks bundle validate` will fail in CI until Plan 01-02 establishes OIDC credentials (DATABRICKS_HOST, DATABRICKS_CLIENT_ID GitHub repository variables). This is expected — Plan 01-02 is the prerequisite for CI/CD to function.

---
*Phase: 01-infrastructure-governance-ci-cd-foundation*
*Completed: 2026-04-07*

## Self-Check: PASSED

All 16 created files confirmed present on disk. Both task commits (910786c, 718c68f) confirmed in git log.
