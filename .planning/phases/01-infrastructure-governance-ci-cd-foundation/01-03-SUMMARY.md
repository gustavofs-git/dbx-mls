---
phase: 01-infrastructure-governance-ci-cd-foundation
plan: "03"
subsystem: infra
tags: [databricks, unity-catalog, uc-grants, databricks-secrets, service-principal]

# Dependency graph
requires:
  - phase: 01-01
    provides: "resources/schemas.yml with lol_analytics catalog declarations (bronze/silver/gold)"
  - phase: 01-02
    provides: "Service Principal identity and OIDC CI/CD workflows"
provides:
  - "lol_analytics catalog with bronze, silver, gold schemas created in Unity Catalog workspace"
  - "UC grants: SP has USE CATALOG and CREATE SCHEMA on lol_analytics"
  - "Databricks Secret Scope lol-pipeline with riot-api-key stored"
  - "SP READ ACL on lol-pipeline scope"
  - "resources/schemas.yml confirmed correct (catalog_name: lol_analytics, all three schemas)"
affects:
  - "01-04-smoke-test"
  - "02-bronze-ingestion"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "UC schema ownership via CI SP first-deploy pattern (SP must deploy first, not human)"
    - "Databricks Secret Scope with explicit READ ACL for SP — not relying on default permissions"

key-files:
  created: []
  modified:
    - "resources/schemas.yml (verified correct — no changes needed from Plan 01-01 state)"

key-decisions:
  - "resources/schemas.yml was already in final state from Plan 01-01 — no code changes required for this plan"
  - "Secret scope lol-pipeline already existed in workspace — create-scope skipped idempotently"
  - "UC grants applied as workspace admin via SQL editor: USE CATALOG + CREATE SCHEMA on lol_analytics"
  - "SP READ ACL granted on lol-pipeline scope before any pipeline execution"

patterns-established:
  - "Pattern: Databricks Secret Scope ACL must be set explicitly for SP — default scope permissions do not include CI service principals"
  - "Pattern: UC GRANT SQL must be run by workspace admin BEFORE first bundle deploy — cannot be automated via DABs"

requirements-completed: [INFRA-02, INFRA-03, INFRA-05]

# Metrics
duration: human-gated
completed: 2026-04-09
---

# Phase 01 Plan 03: Unity Catalog Schemas, SP Ownership Grants, and Databricks Secrets Summary

**lol_analytics catalog wired to SP ownership via UC GRANT SQL and riot-api-key stored in lol-pipeline Databricks Secret Scope with explicit SP READ ACL**

## Performance

- **Duration:** Human-gated (workspace admin steps required external execution)
- **Started:** 2026-04-09
- **Completed:** 2026-04-09
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 0 (resources/schemas.yml already correct from Plan 01-01)

## Accomplishments

- Confirmed `resources/schemas.yml` is in final state with all three schemas under `catalog_name: lol_analytics` — no changes needed
- Human workspace admin created `lol_analytics` catalog with default storage and ran UC GRANT SQL (USE CATALOG + CREATE SCHEMA for SP)
- Databricks Secret Scope `lol-pipeline` existed already; `riot-api-key` stored and SP READ ACL confirmed
- All hard prerequisites for the Plan 01-04 smoke-test are now satisfied

## Task Commits

No code commits were made in this plan — `resources/schemas.yml` was already correct from Plan 01-01. All work was external human infrastructure steps.

1. **Task 1: Verify resources/schemas.yml** — no changes required, file already correct (no commit needed)
2. **Task 2 (checkpoint): UC grants + secret scope** — completed by human in Databricks workspace (no code commit)

**Plan metadata:** (see final docs commit for this plan)

## Files Created/Modified

None — `resources/schemas.yml` was verified correct as-is. No file changes were required.

## Decisions Made

- `resources/schemas.yml` already contained correct `catalog_name: lol_analytics` with bronze, silver, and gold schemas from Plan 01-01 output — no overwrite was needed or performed.
- Secret scope `lol-pipeline` already existed in the workspace; the create-scope step was skipped (idempotent).
- UC GRANT SQL applied minimal required grants: `USE CATALOG` and `CREATE SCHEMA` on `lol_analytics` to the SP — this covers the first bundle deploy creating schemas owned by the SP.
- SP READ ACL on `lol-pipeline` scope granted before any pipeline run — required for `dbutils.secrets.get` to work from SP-owned jobs.

## Deviations from Plan

None — plan executed exactly as written. The only notable detail is that `resources/schemas.yml` was already in final state, so the "write if missing" fallback in Task 1 was not triggered.

## Issues Encountered

None. All human steps completed successfully:
- `lol_analytics` catalog created in Databricks with default storage
- UC grants applied as workspace admin
- Secret scope `lol-pipeline` confirmed existing; SP READ ACL confirmed
- `riot-api-key` stored in `lol-pipeline` scope

## User Setup Required

All user setup for this plan was completed during execution:
- lol_analytics catalog created in Databricks workspace (admin step)
- UC GRANT SQL run as workspace admin: `GRANT USE CATALOG` and `GRANT CREATE SCHEMA` on `lol_analytics` to SP
- `riot-api-key` stored in Databricks Secret Scope `lol-pipeline`
- SP READ ACL granted on `lol-pipeline` scope

## Next Phase Readiness

Ready to execute Plan 01-04 (smoke-test job, end-to-end deploy validation):
- `lol_analytics` catalog exists with bronze/silver/gold schemas ready for SP-first-deploy ownership
- `riot-api-key` is in `lol-pipeline` scope and accessible from SP-owned notebooks
- `resources/schemas.yml` is correct and `databricks bundle validate` passes
- No blockers for Plan 01-04

---
*Phase: 01-infrastructure-governance-ci-cd-foundation*
*Completed: 2026-04-09*
