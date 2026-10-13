# Quotas and retention

Free Edition has usage quotas. Exceeding one disables compute until the next day, which
during a demonstration or a development session is the worst available failure. The platform
is therefore designed to consume a small, predictable amount.

## Where the data is

| Object | Per run | Growth |
|---|---|---|
| landing volume, `.json.gz` | ~250 MB | bounded by retention |
| `bronze.riot_matches` | ~90 MB | unbounded until retention applies |
| `bronze.riot_match_timelines` | ~210 MB | unbounded until retention applies |
| `harmonized.*` | ~40 MB | grows with history; small |
| `consumption.*` | 0 | views |
| `ops.dq_metrics` | kilobytes | negligible |

Roughly **300 MB of compressed Delta plus 250 MB of landing files per weekly run**, or about
2.2 GB per month before retention.

## Retention policy

Applied by the daily `maintain_storage` job.

| Object | Retention | Reason |
|---|---|---|
| landing volume files | **30 days** | their purpose is replay into bronze and resumable fetching; after bronze is validated the file is redundant |
| `bronze.*` | **indefinite** | this is the source of truth; losing it means re-spending the API budget, which is not possible retroactively |
| Delta history (`VACUUM`) | **7 days** | enough for time travel during an incident; the default 30 days triples storage on an append-heavy table |
| `harmonized.*` | indefinite | small, and fully reconstructible from bronze |
| `ops.dq_metrics` | indefinite | kilobytes, and its value is longitudinal |

If storage pressure becomes real, the first lever is reducing bronze timeline retention,
because timelines are 70% of the footprint and the derived `participant_frames` and
`timeline_events` tables are a fraction of the size. That is a deliberate trade of replay
capability for space, and it would be recorded as a superseding ADR rather than applied
quietly.

## Maintenance operations

```sql
OPTIMIZE mls.bronze.riot_matches;
OPTIMIZE mls.harmonized.match_participants;
VACUUM   mls.bronze.riot_matches RETAIN 168 HOURS;
```

Compaction matters here more than usual: weekly batched appends of many small files are
exactly the pattern that degrades Delta read performance.

## Compute discipline

| Practice | Why |
|---|---|
| the `dev` target runs 5 players and 1 match, without timelines | development iterations cost almost nothing |
| CI does not touch the workspace on pull requests | fifteen pushes a day would consume the daily quota in CI |
| the harmonized and consumption layers are developed against **prod bronze** | no re-fetch is needed to iterate on transformations |
| integration tests run weekly or on demand, never per push | see [ADR-0012](../adr/0012-cicd-github-actions-pat.md) |
| the consumption layer materializes nothing | see [ADR-0006](../adr/0006-two-physical-layers-virtual-consumption.md) |

## Monitoring

`ops.dq_metrics` records row counts per table per run. A volumetry chart on the data quality
dashboard is the early warning for storage growth: an unexpected jump in row count precedes
a quota problem by days.

Storage quota itself is **not documented** by Databricks for Free Edition at the time of
writing. Probe V17 in the [validation plan](validation-plan.md) looks for it. Until it
resolves, the policy above is deliberately conservative.
