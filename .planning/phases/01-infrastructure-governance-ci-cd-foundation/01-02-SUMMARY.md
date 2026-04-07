---
phase: 01-infrastructure-governance-ci-cd-foundation
plan: 02
subsystem: infra
tags: [github-actions, oidc, databricks, ci-cd, workload-identity-federation]

# Dependency graph
requires:
  - phase: 01-01
    provides: databricks.yml bundle config, repo scaffold, requirements-dev.txt

provides:
  - ".github/workflows/ci.yml — validate + pytest on every push, OIDC authenticated"
  - ".github/workflows/cd-dev.yml — deploy to dev on push to main, triggers smoke_test_job (branch-scoped OIDC)"
  - ".github/workflows/cd-prod.yml — deploy to prod on v* tags, environment: prod with concurrency guard"
  - "docs/setup.md — OIDC federation setup guide, UC grants, secrets, local dev reference"

affects: [all subsequent phases depend on CI/CD green path and OIDC auth being established]

# Tech tracking
tech-stack:
  added:
    - "GitHub Actions (ci.yml, cd-dev.yml, cd-prod.yml)"
    - "OIDC Workload Identity Federation (DATABRICKS_AUTH_TYPE: github-oidc)"
    - "databricks/setup-cli@v0.295.0 GitHub Action"
    - "actions/setup-python@v5"
    - "actions/checkout@v4"
  patterns:
    - "Branch-scoped OIDC federation policy for dev (no environment: key in job)"
    - "Environment-scoped OIDC federation policy for prod (environment: prod must match subject claim exactly)"
    - "Zero long-lived secrets: all auth via short-lived OIDC tokens"
    - "Tag-triggered prod deploy (v* tags) with manual approval gate via GitHub Environment"
    - "Concurrency group prod-deploy with cancel-in-progress: false prevents parallel prod deploys"

key-files:
  created:
    - ".github/workflows/ci.yml"
    - ".github/workflows/cd-dev.yml"
    - ".github/workflows/cd-prod.yml"
    - "docs/setup.md"
  modified: []

key-decisions:
  - "cd-dev.yml has NO environment: key on the job — branch-scoped federation policy (repo:<org>/dbx-mls:ref:refs/heads/main)"
  - "cd-prod.yml uses environment: prod which must EXACTLY match the federation policy subject environment:prod (case-sensitive)"
  - "CLI pinned to v0.295.0 across all workflows for reproducibility"
  - "docs/setup.md explicitly warns: never run bundle deploy locally before SP deploys via CI (schema ownership risk)"

patterns-established:
  - "OIDC auth pattern: DATABRICKS_AUTH_TYPE + DATABRICKS_HOST + DATABRICKS_CLIENT_ID as repository variables (not secrets)"
  - "Federation policy duality: branch-scoped for dev (no env key in workflow), environment-scoped for prod (env key required)"
  - "Prod safety: environment + concurrency guard prevents accidental parallel deploys"

requirements-completed: [INFRA-01, CICD-01, CICD-02, CICD-03, CICD-04, CICD-05, CICD-06]

# Metrics
duration: 2min
completed: 2026-04-07
---

# Phase 01 Plan 02: GitHub Actions OIDC CI/CD Workflows Summary

**Three OIDC-authenticated GitHub Actions workflows (ci, cd-dev, cd-prod) with zero PAT tokens, plus a lean setup reference guide covering federation policy creation, UC grants, and Riot API key rotation**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-07T17:50:57Z
- **Completed:** 2026-04-07T17:52:xx Z
- **Tasks:** 2 of 3 (Task 3 is a human-verify checkpoint — awaiting green CI confirmation)
- **Files modified:** 4

## Accomplishments

- Three workflow files written verbatim from plan templates — zero PAT tokens, all OIDC
- `ci.yml` runs validate + pytest on every push to any branch
- `cd-dev.yml` deploys to dev on push to main and auto-triggers smoke_test_job (no `environment:` key — branch-scoped OIDC policy)
- `cd-prod.yml` deploys to prod on `v*` tags with `environment: prod`, concurrency guard, and manual approval gate
- `docs/setup.md` covers all four required topics with exact CLI commands and critical case-sensitivity warning

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the three GitHub Actions workflow files** - `7397bd9` (feat)
2. **Task 2: Write docs/setup.md lean reference guide** - `5d22b9f` (feat)
3. **Task 3: Checkpoint — human verify CI green** - awaiting human confirmation

**Plan metadata:** (pending — after checkpoint approval)

## Files Created/Modified

- `.github/workflows/ci.yml` — CI: validate + pytest on every branch push, OIDC via github-oidc auth type
- `.github/workflows/cd-dev.yml` — CD dev: deploy to dev + smoke_test_job on push to main, branch-scoped OIDC
- `.github/workflows/cd-prod.yml` — CD prod: deploy on v* tags, environment: prod, concurrency guard
- `docs/setup.md` — Lean setup reference: OIDC federation, UC grants (all 3 schemas), secrets rotation, local dev

## Decisions Made

- `cd-dev.yml` intentionally has NO `environment:` key — adding `environment: dev` would break OIDC because the dev federation policy subject is branch-scoped (`ref:refs/heads/main`), not environment-scoped
- CLI pinned to `v0.295.0` in all three workflows for reproducibility
- `docs/setup.md` includes explicit "never deploy locally first" warning to prevent schema ownership being claimed by a human identity

## Deviations from Plan

**1. [Rule 1 - Bug] Removed `environment:` string from cd-dev.yml comments**

- **Found during:** Task 1 (acceptance criteria verification)
- **Issue:** Acceptance criteria checks for absence of `environment:` in cd-dev.yml. The explanatory comments initially contained `environment:` literally (e.g., `# NO environment: key here`), which would fail the grep check
- **Fix:** Reworded comments to avoid the literal string while preserving the meaning
- **Files modified:** `.github/workflows/cd-dev.yml`
- **Verification:** `grep -c "environment:" .github/workflows/cd-dev.yml` returns 0
- **Committed in:** `7397bd9` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** Minor comment wording change. No functional impact.

## Issues Encountered

None — all workflow file templates written as specified.

## User Setup Required

Before this plan's checkpoint can be cleared, the following external steps must be completed:

1. **Create Service Principal** at Databricks Account Console
2. **Create dev federation policy** (branch-scoped: `repo:<org>/dbx-mls:ref:refs/heads/main`)
3. **Create prod federation policy** (environment-scoped: `repo:<org>/dbx-mls:environment:prod`)
4. **Add GitHub repository variables**: `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID`
5. **Create GitHub Environment `prod`** with required reviewer protection rule
6. **Add SP to Databricks workspace** with appropriate permissions
7. **Push to main** and observe GitHub Actions → CI + CD Dev must both be green

See `docs/setup.md` Section 1 (OIDC Federation Setup) for exact CLI commands.

## Next Phase Readiness

- All three workflow files are committed and ready to run
- `docs/setup.md` contains all instructions for OIDC setup
- **Blocked at checkpoint:** Human must complete OIDC setup and verify green CI before Plan 01-03 can begin
- Plan 01-03 (Unity Catalog schemas + secrets) depends on the SP existing and having workspace access

---
*Phase: 01-infrastructure-governance-ci-cd-foundation*
*Completed: 2026-04-07 (pending checkpoint clearance)*
