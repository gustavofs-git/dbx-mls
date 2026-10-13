# ADR-0015 — Filter timeline events to four types at the harmonized layer

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

A `match-v5` timeline contains roughly 2,000 events per match across about fifteen event
types. At 650 matches per run, that is 1.3 million rows — roughly two thirds of the entire
platform's row count from a single table.

Most of that volume is low-value: `WARD_PLACED`, `LEVEL_UP`, `SKILL_LEVEL_UP` and
`ITEM_DESTROYED` are high-frequency and answer no question the project asks.

## Decision

Ingest the complete timeline payload into bronze as `VARIANT`, and filter to four event types
when building `harmonized.timeline_events`:

| Event type | Enables |
|---|---|
| `CHAMPION_KILL` | first blood timing, kill participation, snowball analysis |
| `ELITE_MONSTER_KILL` | dragon and baron timing, objective control |
| `BUILDING_KILL` | tower and inhibitor timing, map pressure |
| `ITEM_PURCHASED` | build order and item timing |

This reduces the table to roughly 300,000 rows per run. `participant_frames` is kept in full,
because minute-level economy is the input to gold and experience curves.

The filter is a harmonized-layer decision. Bronze retains every event, so widening the filter
later is a reprocessing job with no API cost.

## Alternatives considered

**All event types.** Rejected: 18 million rows over three months, two thirds of them never
queried, in an environment where storage is the binding constraint.

**No event table, only `participant_frames`.** Cheapest. Rejected: frames describe economy
over time but contain no causality — who killed whom, when an objective fell, what was bought.
That removes the analyses that distinguish the project from a champion win-rate table.

**Filtering at ingestion, before bronze.** Rejected: it would make bronze a transformation
layer and make the decision irreversible without re-spending the API budget.

## Consequences

- Event volume is reduced by roughly 77% for a loss of analyses the project does not perform.
- Widening the filter is a reprocessing operation against existing bronze data, costing
  compute only.
- The chosen set must be stated wherever event-derived metrics are published, because an
  analyst assuming a complete event log would misinterpret counts.
- `timeline_events` is a single wide table with nullable columns per event family rather than
  four narrow tables, because nearly every analysis crosses event types on a shared time axis.
  The nullability is documented in column comments.
