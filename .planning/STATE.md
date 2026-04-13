---
gsd_state_version: 1.0
milestone: v0.295.0
milestone_name: milestone
status: executing
stopped_at: Completed 02-05-PLAN.md — Phase 02 plan 05 complete
last_updated: "2026-04-13T22:37:08.792Z"
last_activity: 2026-04-13
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-07)

**Core value:** A recruiter or hiring manager can run this pipeline end-to-end in under 30
minutes and see a real, parameterized, enterprise-pattern data product — not a tutorial skeleton.

**Current focus:** Phase 02 — bronze-ingestion-pipeline

## Current Position

Phase: 02 (bronze-ingestion-pipeline) — EXECUTING
Plan: 5 of 5
Status: Ready to execute
Last activity: 2026-04-13

Progress: [░░░░░░░░░░] 0%  (0/20 plans complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: — min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| — | — | — | — |

**Recent Trend:** Not yet established

*Updated after each plan completion*
| Phase 01 P01 | 4 | 2 tasks | 16 files |
| Phase 01 P04 | 240 | 2 tasks | 8 files |
| Phase 02-bronze-ingestion-pipeline P02 | 3 | 1 tasks | 6 files |
| Phase 02 P01 | 3 | 2 tasks | 6 files |
| Phase 02 P03 | 3 | 2 tasks | 7 files |
| Phase 02-bronze-ingestion-pipeline P04 | 2 | 2 tasks | 6 files |
| Phase 02-bronze-ingestion-pipeline P05 | 25 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

Key constraints affecting every phase:

- Phase 1: SP must own UC schemas from day one — NEVER run `bundle deploy` locally first
- Phase 1: OIDC subject claim in federation policy must case-sensitively match `environment:`
  key in GitHub Actions workflow

- Phase 2: Dual-bucket rate limiter is mandatory before any volume API calls
- Phase 3: `schemas/match_schema.py` is a hard gate — cannot write Silver without real Bronze data
- Phase 3: `challenges` struct must be flattened to flat `chal_*` columns, NOT kept as STRUCT
- [Phase 01]: workspace.host removed from databricks.yml — CLI v0.295.0 rejects variable interpolation for auth fields; DATABRICKS_HOST env var is the correct mechanism
- [Phase 01]: singleNode cluster profile used (not singleUser — singleUser is a UC access mode, not a cluster profile)
- [Phase 01-infrastructure-governance-ci-cd-foundation]: cd-dev.yml has no environment: key — uses branch-scoped OIDC federation policy (subject: ref:refs/heads/main)
- [Phase 01-infrastructure-governance-ci-cd-foundation]: cd-prod.yml environment: prod must exactly match federation policy subject environment:prod (case-sensitive — silent 401 on mismatch)
- [Phase 01]: Azure OIDC (azure-cli auth type) is the working auth path for this workspace — Databricks OIDC github-oidc auth type requires workspace-level federation policy not available in this tier
- [Phase 01]: Use source: GIT for all DAB job notebook tasks — WORKSPACE source fails due to SP file access restrictions in Unity Catalog workspaces; GIT source pulls from public GitHub at runtime
- [Phase 01]: data_security_mode: SINGLE_USER required on all job clusters in UC workspace — omitting causes cluster rejection
- [Phase 02-bronze-ingestion-pipeline]: Centralized platform routing in src/config.py eliminates 404s — get_region_host() for Match-V5/Account-V1, get_platform_host() for League-Exp-V4/Summoner-V4
- [Phase 02-01]: time.sleep(0.05) in acquire() is lock-release wait only — token bucket IS the primary throttle; sleep must not be used as throttle per plan constraint
- [Phase 02-01]: RiotRateLimiter passed as parameter to call_riot_api() per D-01 — never instantiated internally
- [Phase 02-01]: 404 raises RiotApiError(404, url) explicitly before raise_for_status() — allows downstream to catch 404 vs generic HTTP errors
- [Phase 02]: ingestion_log CREATE TABLE in ingest_league_entries.py only (first DAG task); other notebooks append-write
- [Phase 02]: LEFT ANTI JOIN pre-check in bronze_match_raw.py before any API calls — avoids quota waste on restarts (D-02 pattern)
- [Phase 02]: All bronze MERGE statements use WHEN NOT MATCHED THEN INSERT * only — no UPDATE clause; raw Bronze stores immutable snapshots
- [Phase 02-bronze-ingestion-pipeline]: Summoner-V4 uses PLATFORM host (get_platform_host) — not regional; Account-V1 uses REGIONAL host (get_region_host); timeline anti-join sources from match_raw not match_ids
- [Phase 02-bronze-ingestion-pipeline]: pytest.ini pythonpath=. required for src/ imports without pip install — added as auto-fix
- [Phase 02-bronze-ingestion-pipeline]: summoner_task depends on match_ids_task (parallel to timeline) — reduces wall-clock time for enrichment chain
- [Phase 02-bronze-ingestion-pipeline]: ingestion_job.yml uses timeout_seconds=14400 and source=GIT on all 6 notebook tasks — consistent with Phase 1 SP file access pattern

### Pending Todos

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260410-9jp | fix phase 1 documentation text to match what was actually achieved | 2026-04-10 | 60bc776 | [260410-9jp-fix-phase-1-documentation-text-to-match-](./quick/260410-9jp-fix-phase-1-documentation-text-to-match-/) |

### Blockers / Concerns

- CHALLENGE_FIELDS (125 field names) has MEDIUM confidence from community sources.
  Must validate against a real KR Challenger match JSON response during Plan 03-01.

- Riot Dev API key expires every 24h. Document rotation process in Phase 1 `docs/setup.md`.
- DAB job `timeout_seconds` must be set to 14400 (4 hours) — cold run takes 2-3.5h at dev key rate.

## Session Continuity

Last session: 2026-04-13T22:37:08.790Z
Stopped at: Completed 02-05-PLAN.md — Phase 02 plan 05 complete
Resume file: None
