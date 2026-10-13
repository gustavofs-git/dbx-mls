# ADR-0014 — Weekly ingestion, daily maintenance job

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

Three forces pull in different directions.

Accumulating history is what makes the dataset interesting: a single snapshot answers "what
is the meta" but not "how did it move". Storage is the binding constraint, at roughly 300 MB
of compressed Delta per run. And a Free Edition account that goes inactive may be deleted,
so something must run regularly regardless of ingestion cadence.

League of Legends ships a balance patch roughly every two weeks, which sets the natural
frequency of the underlying phenomenon.

## Decision

| Job | Cadence | Work |
|---|---|---|
| `ingest_and_transform_challenger` | weekly | full scope fetch, about 26 minutes, about 300 MB |
| `maintain_storage` | daily | `OPTIMIZE`, `VACUUM`, apply landing-zone retention, write freshness metrics, health check |

Weekly ingestion samples each patch at least twice, which is the minimum for a before-and-
after comparison. The daily maintenance job keeps the account active at negligible compute
cost and performs work the platform genuinely needs.

During development, ingestion is run manually against the `dev` target at minimum scope
rather than on a schedule.

## Alternatives considered

**Daily ingestion.** Finer granularity. Rejected: roughly 2 GB per week with no analytical
gain, since the meta does not move daily, and a materially higher risk of quota exhaustion.

**A single deep backfill with no schedule.** Cheapest, and sufficient for screenshots.
Rejected: it produces a snapshot rather than a time series, so patch comparison — the core of
the business question — becomes impossible, and the inactivity risk is unaddressed.

**Fortnightly, aligned to the patch calendar.** Analytically defensible and cheaper. Rejected
as too sparse for the project's lifetime: two months of running would yield four data points.

**A trivial no-op job purely to keep the account alive.** Rejected: maintenance is real work
the platform needs — Delta files require compaction and the landing zone requires retention —
so a job that does it is honest, while a heartbeat that does nothing is a workaround
pretending to be a job.

## Consequences

- Roughly 1.2 GB of compressed Delta accrues per month before retention.
- Patch-over-patch comparison becomes available after about one month of operation.
- Weeks where the Riot key is not refreshed produce a recorded skip and a gap in history.
  This is accepted; see [ADR-0001](0001-platform-databricks-free-edition.md).
- The maintenance job is the only thing standing between the account and deletion, so its
  failure notification matters more than its content.
