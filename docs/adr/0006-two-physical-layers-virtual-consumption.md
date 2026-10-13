# ADR-0006 — Two physical layers, virtual consumption layer

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The textbook medallion architecture materializes three layers: bronze, silver, gold. Most
data engineering portfolios implement exactly that, and the third layer is usually adopted by
convention rather than by requirement.

Two things make the convention worth questioning here.

**The data is small.** At the scope in [ADR-0003](0003-data-source-scope-kr-challenger.md),
three months of weekly runs produce roughly 8,000 matches, 78,000 participant rows and 2.3
million frame rows. A 2X-Small SQL warehouse aggregates that in views without difficulty.
Materializing an aggregate of 78,000 rows costs storage, compute, a scheduled job that can
fail, and a staleness window, in exchange for a latency improvement nobody can perceive.

**The industry is actively moving.** There is a visible trend toward `bronze → harmonized →
consumers`, where the harmonized layer is the conformed asset and metrics are defined
declaratively — as views, metric views or a semantic layer — rather than materialized per
consumer. The drivers are gold-table proliferation, per-consumer bespoke extracts that nobody
can retire, and the operational weight of pipelines whose only purpose is pre-computing a
`GROUP BY`.

## Decision

Two materialized layers and one virtual layer:

| Layer | Form | Content |
|---|---|---|
| `bronze` | Delta tables | raw payload as `VARIANT` plus call metadata |
| `harmonized` | Delta tables | flattened, typed, deduplicated, pseudonymized, validated entities |
| `consumption` | **views** | `dim_*`, `fct_*`, `agg_*` — a full dimensional model, materializing nothing |

The dimensional model is not abandoned. `dim_champion`, `dim_patch`, `fct_match_participant`
and the aggregates all exist, are auditable, and carry a star-schema design with stated grain
and stated denominators. They simply occupy no storage and require no pipeline.

Materialization becomes a decision that must be **earned by a measured requirement**, and
earning it is a `CREATE TABLE AS SELECT` away.

## Alternatives considered

**Classic three materialized layers.** The conventional answer, and the safe one for a
portfolio: dimensional modeling is among the most-assessed skills in data engineering
interviews, and materialized `fct_`/`dim_` tables are its most legible evidence. Rejected
because the materialization cannot be justified at this volume, and because stating the
reasoning is stronger evidence of the skill than performing the convention. The risk is real
and acknowledged: a reader who skims may see "no gold tables" and stop there, which is why
the dimensional model is named, documented and diagrammed as prominently as if it were
materialized.

**Two layers with no dimensional model — harmonized consumed directly.** Closest to the trend
being described, and the simplest. Rejected: it discards the conformed-model layer that makes
measures comparable, and it would leave each consumer to re-derive pick rate and ban rate with
its own denominator. Stated metric definitions are the main value of a consumption layer, and
a flat harmonized table does not provide them.

**Metric views or a semantic layer instead of SQL views.** Attractive and closer to where the
industry is heading. Deferred rather than rejected: availability on Free Edition is
unverified, and introducing an unproven platform feature into the core design would risk the
whole consumption layer. On the roadmap.

## Consequences

- Nothing in `consumption` can be queried faster than the underlying `harmonized` scan. If a
  dashboard becomes slow, the fix is to materialize one specific view, which is a reversible,
  one-statement change.
- The claim "two physical layers" is literally true, which matters: a project that advertises
  an alternative architecture and ships a conventional one with a renamed layer would not
  survive a critical reading.
- Storage is spent only on raw and conformed data, which is the right place to spend it when
  storage is the binding constraint.
- Business-scope filtering lives in exactly four fact views, making "should remakes count?"
  and "should ARAM count?" one-line, reviewable changes rather than reprocessing jobs. See
  [ADR-0008](0008-data-quality-strategy.md).
- When the public showcase is designed, it will need one materialized aggregate as its export
  surface. That will be the first and only earned materialization, and it will be recorded as
  such.
