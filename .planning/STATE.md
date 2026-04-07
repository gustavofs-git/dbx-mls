# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-07)

**Core value:** A recruiter or hiring manager can run this pipeline end-to-end in under 30
minutes and see a real, parameterized, enterprise-pattern data product — not a tutorial skeleton.

**Current focus:** Phase 1 — Infrastructure, Governance & CI/CD Foundation

## Current Position

Phase: 1 of 5 (Infrastructure, Governance & CI/CD Foundation)
Plan: 0 of 4 in current phase
Status: Ready to plan
Last activity: 2026-04-07 — ROADMAP.md and STATE.md initialized after research phase

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

### Pending Todos

None yet.

### Blockers / Concerns

- CHALLENGE_FIELDS (125 field names) has MEDIUM confidence from community sources.
  Must validate against a real KR Challenger match JSON response during Plan 03-01.
- Riot Dev API key expires every 24h. Document rotation process in Phase 1 `docs/setup.md`.
- DAB job `timeout_seconds` must be set to 14400 (4 hours) — cold run takes 2-3.5h at dev key rate.

## Session Continuity

Last session: 2026-04-07
Stopped at: Roadmap and state initialization complete — all 47 requirements mapped to 20 plans across 5 phases
Resume file: None
