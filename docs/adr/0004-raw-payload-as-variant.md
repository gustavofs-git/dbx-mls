# ADR-0004 — Store the raw API payload as `VARIANT`

- **Status:** Accepted, pending validation
- **Date:** 2026-10-09

## Context

A `match-v5` response is deeply nested, around 400 KB, and contains several hundred fields
across ten participants, including a `challenges` object with roughly 150 metrics. Riot adds
fields between patches without notice.

The bronze layer must preserve the response exactly. The question is what column type holds
it.

## Decision

Store it in a `VARIANT` column.

```sql
payload VARIANT COMMENT 'Unmodified API response body'
```

Access at the harmonized boundary uses native navigation:

```sql
payload:info.gameVersion::string
payload:info.participants   -- an array, expandable without a declared schema
```

Acceptance is conditional on a feasibility probe confirming that `VARIANT` works on Free
Edition serverless compute **and** inside a Lakeflow declarative pipeline. If it does not,
this record is superseded by a `STRING` variant.

## Alternatives considered

**`STRING` holding the JSON text.** Universal, mature, works in open-source PySpark.
Rejected for four reasons: the engine decompresses and scans the entire document for every
query regardless of how few fields are referenced; all values return as text, requiring a
cast per field; expanding nested arrays requires `from_json` with a **declared schema**, which
reintroduces exactly the schema-drift fragility the raw layer exists to avoid; and a field
Riot adds is silently dropped by that declared schema rather than quietly preserved.

**Typed `STRUCT` columns parsed at ingestion.** Rejected outright: it makes bronze a
transformation layer, and a schema change upstream breaks ingestion rather than being absorbed.

**Files only, with no bronze table.** Rejected: no SQL surface, no Unity Catalog lineage, no
time travel. See [ADR-0005](0005-landing-zone-before-bronze.md) for why files exist *as well*.

## Consequences

**Gained.** No schema is ever declared over the raw payload, so Riot's additions are absorbed
and available retroactively. Reads touch only the referenced fields. Original JSON types —
number, boolean, null — survive the round trip. Query syntax is readable.

**Accepted costs.**

- `VARIANT` is a recent Databricks Runtime type. Community material is thin, and debugging a
  problem will be slower than it would be with `STRING`.
- There is a **16 MB limit per `VARIANT` value**. Timeline payloads are 2–5 MB, so the margin
  is roughly 3×. If Riot expands timeline payloads substantially, this becomes a hard failure
  and the fallback is to store timelines as `STRING` while keeping match detail as `VARIANT`.
- A `VARIANT` column cannot be used directly as a join key or in `ORDER BY`; a field must be
  extracted first. This is why `match_id` is also stored as a `STRING` column.
- `VARIANT` may not exist in open-source PySpark, which runs the unit tests in CI. The
  mitigation is structural: all `VARIANT` navigation syntax is confined to
  `src/mls/transforms/extract.py`, and every other transform operates on already-extracted
  DataFrames so that it remains testable off-platform. Confirmed or refuted by the
  [validation plan](../operations/validation-plan.md).
- Downstream tools and connectors may not understand the type. Irrelevant here, since nothing
  outside Databricks reads bronze.

**Not gained.** `VARIANT` solves *schema flexibility*. It does nothing for *data validity*: a
`kills` value of `-1` is stored with perfect fidelity. Validity is handled separately in
[ADR-0008](0008-data-quality-strategy.md).
