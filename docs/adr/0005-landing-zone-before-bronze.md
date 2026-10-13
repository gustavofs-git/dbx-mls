# ADR-0005 — Land raw responses as files before writing bronze

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

API data is expensive and perishable here: a full run costs about 26 minutes of rate-limited
calls, and the development key expires every 24 hours. Re-fetching is not a cheap recovery
path.

If the only persistence of a response is the bronze table row written in the same process
that made the call, then any failure between the HTTP response and the successful table
commit loses data that cannot be recovered without spending the request budget again.

## Decision

Write each raw response to a file in a Unity Catalog volume first, then build bronze from
those files with Auto Loader.

```
/Volumes/mls/landing/raw_riot/match_v5/dt=2026-10-09/KR_7891234567.json.gz
```

The file name is deterministic. An existing file short-circuits the HTTP call, which makes a
re-run of a partially failed ingestion fetch only what is missing.

## Alternatives considered

**Bronze table only, no files.** Considered seriously and nearly adopted. The argument for it
is strong: if bronze is genuinely as-is — payload plus call metadata, no parsing — then there
is almost nothing about its shape that can be wrong, so the ability to rebuild it is of
little value, and the second copy is pure cost. Batched appends plus idempotency on
`match_id` also provide checkpointing without files.

Rejected on one point: the second copy is not insurance against a *wrong table shape*, it is
insurance against **losing the response at all**. The landing file exists before any Spark
write is attempted, and the deterministic file name is what makes the fetch resumable without
re-spending requests.

**Files only, bronze as an external or streaming read.** Rejected: no Unity Catalog lineage,
no time travel, no reasonable SQL surface over raw data.

**A rotating buffer store (the pattern of an operational MongoDB in front of bronze).**
Rejected as unavailable: Free Edition offers no such store, and the landing volume plays
exactly that role — a holding area whose contents are expendable once bronze has them.

## Consequences

- Raw data is stored twice. Gzipped files are roughly 250 MB per run against roughly 300 MB
  in Delta; retention keeps this bounded — see
  [quotas and retention](../operations/quotas-and-retention.md).
- Auto Loader has a genuine role: incremental file discovery with a checkpoint, exactly-once
  processing, and `meta_source_file` provenance down to the row. It is used because there is a
  file-based landing zone, not to put a named feature on a résumé.
- Bronze becomes fully reconstructible from files without touching the Riot API, which makes
  a change to the bronze table definition a low-risk operation.
- Ingestion and modeling are decoupled: the job that spends the request budget has one
  responsibility, and failures in it are distinguishable from failures in transformation.
