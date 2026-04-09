---
phase: 01-infrastructure-governance-ci-cd-foundation
plan: "04"
subsystem: infra
tags: [databricks, dabs, smoke-test, oidc, azure-oidc, unity-catalog, github-actions, linkedin]

# Dependency graph
requires:
  - phase: 01-03
    provides: UC schemas created with SP ownership, Databricks Secret Scope lol-pipeline with riot-api-key
  - phase: 01-02
    provides: GitHub Actions CI/CD workflows with OIDC authentication, cd-dev.yml with bundle run trigger

provides:
  - Permanent smoke test notebook (notebooks/smoke_test.py) with three infrastructure validations
  - DAB job definition (resources/jobs/smoke_test_job.yml) that runs on every dev deploy
  - Phase 1 LinkedIn article (docs/posts/phase-1-article.md) — full technical walkthrough
  - Phase 1 LinkedIn short post (docs/posts/phase-1-post.md) — ~150 words, OIDC zero-secrets hook
  - End-to-end verified CI pipeline: push to main produces CI green + CD Dev green + SMOKE TEST PASSED

affects: [phase-02-bronze-ingestion, phase-03-silver-transformation]

# Tech tracking
tech-stack:
  added:
    - Azure OIDC via azure/login action (replaced Databricks OIDC flow)
    - GIT source for DAB job notebook (vs WORKSPACE source)
    - data_security_mode: SINGLE_USER for Unity Catalog cluster compliance
  patterns:
    - Smoke test as permanent infrastructure health gate — runs on every dev deploy
    - GIT source notebook delivery: job pulls notebook from public GitHub repo at runtime
    - Azure OIDC (azure-cli auth type) as the working authentication path for azure-cli installed CLI

key-files:
  created:
    - notebooks/smoke_test.py
    - resources/jobs/smoke_test_job.yml
    - docs/posts/phase-1-article.md
    - docs/posts/phase-1-post.md
  modified:
    - .github/workflows/ci.yml (Azure OIDC, azure/login, sp_client_id var)
    - .github/workflows/cd-dev.yml (Azure OIDC, azure/login, --auto-approve, GIT source path)
    - requirements-dev.txt (pyspark bumped to 3.5.3)
    - databricks.yml (sp_client_id variable, dev root_path fixed)

key-decisions:
  - "Switched from Databricks OIDC to Azure OIDC (azure/login + azure-cli auth type) — Databricks OIDC required workspace-level federation policy config not available in this workspace tier; Azure OIDC uses azure-cli auth which works with the existing SP and OIDC token"
  - "Smoke test uses GIT source (source: GIT) — WORKSPACE source failed because job cluster could not access SP-owned workspace files; GIT source pulls notebook directly from public GitHub at runtime, eliminating permission issue"
  - "data_security_mode: SINGLE_USER required — Unity Catalog workspace enforces access mode on all clusters; omitting it caused job cluster rejection"
  - "Removed persistent cluster (clusters.yml deleted) — no code reuse across plans, persistent cluster was cost waste; smoke test job defines its own ephemeral job_cluster"
  - "dev target uses fixed Shared root_path — mode: development with user-prefixed path caused SP permission failures; fixed path in /Workspace/Shared resolves cluster file access"
  - "bundle deploy with --auto-approve required in CI — interactive prompt caused CD workflow hang"

patterns-established:
  - "GIT source pattern: DAB job notebook_task with source: GIT + git_source block pulls from public GitHub at runtime — avoids workspace file permission issues for SP-owned deploys"
  - "Azure OIDC pattern: azure/login with allow-no-subscriptions + DATABRICKS_AUTH_TYPE: azure-cli is the working auth flow for this workspace configuration"
  - "Smoke test is a permanent fixture: smoke_test_job in resources/jobs/ is never removed — becomes the baseline health check for all future phases"

requirements-completed: [INFRA-06, AGTC-04]

# Metrics
duration: ~4h (including multiple fix iterations)
completed: 2026-04-09
---

# Phase 01 Plan 04: Smoke Test, End-to-End Validation, and LinkedIn Deliverables Summary

**Permanent smoke test job validating Databricks secrets, Unity Catalog access, and Delta table roundtrip on every dev deploy — with full Phase 1 LinkedIn article and short post**

## Performance

- **Duration:** ~4 hours (including infrastructure fix iterations)
- **Started:** 2026-04-09
- **Completed:** 2026-04-09
- **Tasks:** 2 (plus checkpoint verification)
- **Files modified:** 8

## Accomplishments

- Smoke test notebook and DAB job definition created and running in production — `SMOKE TEST PASSED` confirmed in Databricks job logs
- CI pipeline end-to-end verified: push to `main` triggers CI green + CD Dev green + smoke job completion
- Riot API key confirmed retrievable from Databricks Secret Scope with value `[REDACTED]` in all logs
- Unity Catalog access confirmed from job cluster: bronze, silver, gold schemas visible
- Bronze table roundtrip confirmed: create + insert + read + drop all succeeded
- Phase 1 LinkedIn article (full technical walkthrough) and short post (~150 words) committed to docs/posts/

## Task Commits

1. **Task 1: Smoke test notebook and DAB job definition** - `d402a7c` (feat)
2. **Task 2: Phase 1 LinkedIn deliverables** - `04d4b35` (feat)

**Infrastructure fix commits (post-task, pre-checkpoint):**
- `3fd2be2` — Switch from Databricks OIDC to Azure OIDC (azure-cli auth)
- `29a8cbc` — allow-no-subscriptions on azure/login
- `f7e7ff9` — Remove subscription-id from azure/login
- `288286e` — Bump pyspark to 3.5.3 for delta-spark constraint
- `d9814ea` — Pass sp_client_id bundle variable from DATABRICKS_CLIENT_ID
- `af3b402` — Add data_security_mode SINGLE_USER and ResourceClass tag
- `8b2c269` / `63fd5d3` — Fix dev root_path for SP workspace access
- `0e73e79` / `45b4245` — SP CAN_MANAGE grant on bundle path
- `c75b851` — Deploy to SP own workspace path
- `8fabb3b` — Add --auto-approve to bundle deploy
- `ff32006` / `3856289` — Switch smoke test to GIT source
- `f3e3794` — Remove persistent cluster, switch to Standard_F2s_v2
- `0e7ddad` — Revert to Standard_F4s_v2 (minimum supported in workspace)

## Files Created/Modified

- `notebooks/smoke_test.py` — Databricks notebook with three infrastructure validations (secrets, UC access, bronze table roundtrip)
- `resources/jobs/smoke_test_job.yml` — Permanent DAB job definition: ephemeral Standard_F4s_v2 cluster, GIT source, timeout_seconds 14400
- `docs/posts/phase-1-article.md` — Full LinkedIn article: OIDC architecture, DABs, UC ownership bootstrap, three-workflow CI/CD, smoke test design, Claude-as-Robin callout
- `docs/posts/phase-1-post.md` — Short LinkedIn post (~150 words): OIDC zero-secrets hook, four bullet points, article CTA
- `.github/workflows/ci.yml` — Azure OIDC auth, azure/login step, DATABRICKS_AUTH_TYPE: azure-cli, BUNDLE_VAR_sp_client_id
- `.github/workflows/cd-dev.yml` — Azure OIDC auth, --auto-approve on deploy, smoke_test_job run trigger
- `requirements-dev.txt` — pyspark bumped to 3.5.3 (required by delta-spark 3.3.2)
- `databricks.yml` — sp_client_id variable, dev target fixed root_path

## Decisions Made

**Azure OIDC over Databricks OIDC:** The Databricks GitHub OIDC flow (DATABRICKS_AUTH_TYPE: github-oidc) requires a federation policy at the workspace level that was not available in this workspace configuration. Switching to Azure OIDC (azure/login action + DATABRICKS_AUTH_TYPE: azure-cli) uses the Service Principal's Azure AD identity, which the Databricks CLI then uses via azure-cli auth. This is the correct pattern for Azure-hosted workspaces where the SP has Azure AD app registration.

**GIT source for smoke test notebook:** The initial plan used `source: WORKSPACE` with the notebook deployed into the workspace via bundle deploy. This failed because the job cluster could not access files in the SP-owned workspace path. Switching to `source: GIT` with a `git_source` block pointing to the public GitHub repo eliminates the workspace file access issue entirely — the cluster pulls the notebook directly from GitHub at job runtime.

**Removed persistent cluster:** The original plan referenced a `resources/clusters.yml` with a shared cluster definition. This was removed because (1) no jobs share a cluster across phases, (2) the persistent cluster incurs cost when idle, and (3) each job defining its own ephemeral `job_cluster` is the correct DABs pattern for cost-conscious portfolio projects.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Switched from Databricks OIDC to Azure OIDC**
- **Found during:** Post-task fix iteration (CI pipeline validation)
- **Issue:** `DATABRICKS_AUTH_TYPE: github-oidc` failed with authentication error — workspace-level federation policy config not available
- **Fix:** Added `azure/login` action step with `allow-no-subscriptions: true`, changed auth type to `azure-cli`
- **Files modified:** .github/workflows/ci.yml, .github/workflows/cd-dev.yml
- **Verification:** CI and CD Dev workflows both green after fix
- **Committed in:** 3fd2be2, 29a8cbc, f7e7ff9

**2. [Rule 1 - Bug] Fixed pyspark version constraint**
- **Found during:** Post-task fix iteration (CI pip install)
- **Issue:** `pyspark==3.5.2` incompatible with `delta-spark==3.3.2` which requires `pyspark>=3.5.3`
- **Fix:** Bumped pyspark to `3.5.3` in requirements-dev.txt
- **Files modified:** requirements-dev.txt
- **Verification:** pip install succeeds in CI
- **Committed in:** 288286e

**3. [Rule 2 - Missing Critical] Added BUNDLE_VAR_sp_client_id to CI workflows**
- **Found during:** Post-task fix iteration (bundle deploy failure)
- **Issue:** `databricks bundle deploy` failed because `sp_client_id` variable was declared in databricks.yml but not supplied in CI environment
- **Fix:** Added `BUNDLE_VAR_sp_client_id: ${{ vars.DATABRICKS_CLIENT_ID }}` env var to both workflows
- **Files modified:** .github/workflows/ci.yml, .github/workflows/cd-dev.yml
- **Verification:** Bundle validate and deploy succeed after fix
- **Committed in:** d9814ea

**4. [Rule 1 - Bug] Added data_security_mode: SINGLE_USER to cluster config**
- **Found during:** Post-task fix iteration (smoke test job cluster start)
- **Issue:** Unity Catalog workspace rejected job cluster without explicit data_security_mode — cluster failed to start
- **Fix:** Added `data_security_mode: SINGLE_USER` and `ResourceClass: SingleNode` tag to job_clusters config in smoke_test_job.yml
- **Files modified:** resources/jobs/smoke_test_job.yml
- **Verification:** Job cluster starts successfully, smoke test completes
- **Committed in:** af3b402

**5. [Rule 1 - Bug] Switched smoke test notebook to GIT source**
- **Found during:** Post-task fix iteration (smoke test job run failure)
- **Issue:** WORKSPACE source failed — job cluster could not access SP-owned workspace files at deployed path; multiple fix attempts (DBFS, CAN_MANAGE grants, root_path adjustments) all failed
- **Fix:** Replaced `source: WORKSPACE` with `source: GIT` and added `git_source` block pointing to public GitHub repo; notebook_path changed to `notebooks/smoke_test`
- **Files modified:** resources/jobs/smoke_test_job.yml
- **Verification:** Job run succeeds, SMOKE TEST PASSED in logs
- **Committed in:** 3856289

**6. [Rule 1 - Bug] Removed persistent cluster, fixed cluster node type**
- **Found during:** Post-task fix iteration (cluster cost and compatibility)
- **Issue:** clusters.yml with persistent cluster was unnecessary cost; Standard_F2s_v2 not supported in workspace (minimum is Standard_F4s_v2)
- **Fix:** Deleted clusters.yml; smoke test job defines its own ephemeral job_cluster with Standard_F4s_v2
- **Files modified:** resources/clusters.yml (deleted), resources/jobs/smoke_test_job.yml
- **Verification:** Job runs successfully with F4s_v2 ephemeral cluster
- **Committed in:** f3e3794, 0e7ddad

**7. [Rule 2 - Missing Critical] Added --auto-approve to bundle deploy**
- **Found during:** Post-task fix iteration (CD Dev workflow hang)
- **Issue:** `databricks bundle deploy` prompted for confirmation in non-interactive CI environment, causing workflow timeout
- **Fix:** Added `--auto-approve` flag to bundle deploy step in cd-dev.yml
- **Files modified:** .github/workflows/cd-dev.yml
- **Verification:** CD Dev workflow completes without hanging
- **Committed in:** 8fabb3b

---

**Total deviations:** 7 auto-fixed (4 bugs, 3 missing critical)
**Impact on plan:** All fixes were necessary for the CI pipeline to function end-to-end. The core deliverables (smoke test notebook, job definition, LinkedIn content) matched the plan exactly. The infrastructure fixes resolved auth, cluster, and file-access gaps in the original configuration that only surfaced during actual CI execution.

## Issues Encountered

The primary challenge was the authentication chain: Databricks OIDC (github-oidc auth type) did not work with this workspace's federation policy configuration. Switching to Azure OIDC resolved this but required understanding that `DATABRICKS_AUTH_TYPE: azure-cli` is the correct value when using azure/login to authenticate the CLI indirectly via Azure AD.

The second major issue was notebook delivery: WORKSPACE source required the job cluster to access files in a path owned by the SP after deploy. Multiple approaches (DBFS, CAN_MANAGE grants, different root_path values) all failed due to Unity Catalog workspace file access restrictions. GIT source completely bypassed this constraint.

Both issues are documented as key architectural lessons for Phase 2.

## Next Phase Readiness

Phase 1 is complete. All success criteria verified in production:
- Push to `main` produces CI green + CD Dev green + `SMOKE TEST PASSED` in Databricks logs
- Riot API key value is `[REDACTED]` in all logs
- Unity Catalog schemas bronze/silver/gold confirmed accessible from job cluster
- SP ownership confirmed on all three schemas
- Zero credential file leakage (git status clean)

Phase 2 (Bronze Ingestion) can begin. The smoke test job will continue running on every dev deploy as an infrastructure health gate alongside Phase 2 job definitions.

Key constraint carried forward: notebook delivery to Databricks jobs must use `source: GIT` with a public GitHub repo — do not use `source: WORKSPACE` for job tasks in this workspace configuration.

---
*Phase: 01-infrastructure-governance-ci-cd-foundation*
*Completed: 2026-04-09*
