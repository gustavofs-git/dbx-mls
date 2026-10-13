# Roadmap

Work is organized as **initiative → epic → ticket** in GitHub Issues, matching the hierarchy
described in [ways of working](ways-of-working.md).

The ordering is driven by dependency, not by interest. The two rules that produced it:
**prove the platform before building on it**, and **do not build a layer whose input does not
exist yet**.

## Initiative

> **mylolstats — a portfolio data platform on Databricks Free Edition**
> Ingest KR Challenger match data from the Riot API and publish high-elo meta analytics,
> engineered as a professional delivery: IaC, CI/CD, data quality, privacy, observability and
> a written record of every decision.

## Epic 0 — Foundations and feasibility

Nothing else may start until the blocking probes pass. A failure here supersedes an ADR, and
discovering that in Epic 4 would waste everything built on the assumption.

| # | Ticket | Done when |
|---|---|---|
| 0.1 | Repository scaffolding: `uv`, `ruff`, `pytest`, `pre-commit`, package layout | `uv run pytest` passes on an empty suite; hooks block a planted secret |
| 0.2 | Install and authenticate the Databricks CLI | probe **V1** passes |
| 0.3 | Obtain a Riot development key; apply for a personal key | key stored in the secret scope; application submitted |
| 0.4 | Run blocking probes **V2–V10** | results recorded in the [validation plan](../operations/validation-plan.md) |
| 0.5 | Run non-blocking probes **V11–V17** | results recorded; affected ADRs updated |
| 0.6 | Minimal bundle: one trivial job, deployed to both targets | `bundle deploy -t dev` and `-t prod` both succeed |
| 0.7 | CI workflows `ci.yml` and `deploy.yml` | a pull request runs lint, tests and `bundle validate` |
| 0.8 | Docs site: MkDocs, `docs.yml`, GitHub Pages | the site builds and publishes on merge |
| 0.9 | Agent tooling: `CLAUDE.md`, the five skills, the `dbx-validator` subagent | all versioned in the repository and used at least once |

## Epic 1 — Unity Catalog foundation

| # | Ticket | Done when |
|---|---|---|
| 1.1 | Catalogs, schemas and the landing volume declared in the bundle | `bundle deploy` creates them from nothing |
| 1.2 | Bronze table DDL with `VARIANT` payload and `meta_*` columns | tables exist with column comments populated |
| 1.3 | Secret scope and the pseudonymization salt | documented in the runbook; salt backed up offline |

## Epic 2 — Ingestion: API to landing zone

The first epic that spends the request budget. Everything downstream depends on its output.

| # | Ticket | Done when |
|---|---|---|
| 2.1 | `RiotClient`: token-bucket rate limiting, retry, backoff, routing | unit tested against recorded fixtures, including 429 and 403 paths |
| 2.2 | `TokenManager`: read the secret, probe the key, report validity | an invalid key produces a recorded skip, not a failure |
| 2.3 | `Logger` and `RunContext` | structured output is legible in the Databricks task log |
| 2.4 | `BaseIngestor` template method | adding an endpoint requires one subclass |
| 2.5 | `LeagueV4Ingestor`: Challenger ladder to the landing zone | ~300 players landed |
| 2.6 | `MatchV5Ingestor`: match ids, detail and timeline, with deduplication | ~650 distinct matches landed; re-run fetches nothing new |
| 2.7 | `conf/ingestion_scope.yml` wired to bundle variables | dev runs 5 players, prod runs 300, from one codebase |

## Epic 3 — Bronze

| # | Ticket | Done when |
|---|---|---|
| 3.1 | Auto Loader from the landing volume into bronze | files processed exactly once; `meta_source_file` populated |
| 3.2 | Idempotency on the natural key | re-running the pipeline produces no duplicates |
| 3.3 | Bronze volumetry metrics into `ops.dq_metrics` | row counts recorded per run |

## Epic 4 — Harmonized

| # | Ticket | Done when |
|---|---|---|
| 4.1 | `transforms/extract.py`: the only module touching `VARIANT` syntax | isolated so that every other transform is testable off-platform |
| 4.2 | `BaseBronzeToHarmonized` template method and the registry | adding an entity requires one class |
| 4.3 | `pseudonymize.py`: HMAC conversion | stability tested; salt proven absent from logs |
| 4.4 | `matches`, `match_participants`, `match_teams` | grains correct; expectations applied; drop counts recorded |
| 4.5 | `participant_frames`, `timeline_events` with the four-type filter | volumes within the estimates in [ADR-0015](../adr/0015-timeline-event-type-filtering.md) |
| 4.6 | `league_entries` snapshots | one dated row per player per run |
| 4.7 | DQ measurements: volumetry, freshness, fullness, validity, uniqueness | `ops.dq_metrics` populated for every harmonized table |

## Epic 5 — Consumption

| # | Ticket | Done when |
|---|---|---|
| 5.1 | Dimension views and the `dim_queue` seed | grains documented |
| 5.2 | Fact views with the business-scope filter stated once | remakes and non-ranked queues excluded in exactly four places |
| 5.3 | Aggregate views with explicit denominators | pick rate, ban rate and win rate each state what they divide by |
| 5.4 | Unity Catalog comments and tags on every object | no table or column without a comment |

## Epic 6 — Orchestration and operations

| # | Ticket | Done when |
|---|---|---|
| 6.1 | `ingest_and_transform_challenger` job with both tasks | weekly schedule active on prod, paused on dev |
| 6.2 | `maintain_storage` job: `OPTIMIZE`, `VACUUM`, retention, health check | runs daily; keeps the account active |
| 6.3 | Failure notifications declared in the bundle | a forced failure produces an email |
| 6.4 | `integration.yml` workflow | a manual run deploys to dev, runs the job and asserts the tables |

## Epic 7 — Observability

| # | Ticket | Done when |
|---|---|---|
| 7.1 | Data quality dashboard: volumetry, freshness, fullness, drop rate | one dashboard, screenshot-ready |
| 7.2 | Analytics dashboard on the consumption layer | answers the business question for the current patch |
| 7.3 | Weekly natural-language meta summary | **conditional** on probe V12 |

## Epic 8 — Documentation and publication

| # | Ticket | Done when |
|---|---|---|
| 8.1 | Data dictionary generated from Unity Catalog comments | published on the docs site |
| 8.2 | README as the shop window: thesis, diagram, stack, how to reproduce, CI badges | a stranger understands the project in two minutes |
| 8.3 | Agent orchestration write-up: skills, subagent, what was delegated and what was reviewed | inspectable against the versioned definitions |
| 8.4 | The long-form article, assembled from the ADRs | published |
| 8.5 | Demo video, 3–5 minutes | linked from the README |

## Deferred

| Item | Status | Reason |
|---|---|---|
| Public showcase: export, hosting, dashboard | **pending a decision** | see [open decisions](open-decisions.md) |
| Machine learning: win prediction from minute-15 features | phase 2 | [ADR-0016](../adr/0016-ai-usage-scope.md) |
| Data Dragon enrichment of `dim_champion` | phase 2 | champion class, release date, icons |
| Grandmaster and Master tiers; a second region | phase 2 | [ADR-0003](../adr/0003-data-source-scope-kr-challenger.md) |
| Unfiltered timeline events | phase 2 | [ADR-0015](../adr/0015-timeline-event-type-filtering.md) |
| Metric views in place of SQL views | phase 2 | conditional on probe V13 |
| Great Expectations as a profiling layer | phase 2 | [ADR-0009](../adr/0009-native-expectations-over-external-dq.md) |
