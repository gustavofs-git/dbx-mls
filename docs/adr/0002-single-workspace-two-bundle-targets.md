# ADR-0002 — One workspace, two bundle targets, catalog per target

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

Free Edition provides exactly one workspace, so separate development and production
environments are not available. At the same time, the bronze layer is **append-only**: a
buggy ingestion run cannot be corrected by re-running it, and its output persists until rows
are deleted by hand — which defeats the purpose of an immutable raw layer.

Development will involve many failed and partial ingestion runs. Those runs must not write
into the bronze layer that feeds published output.

The harmonized and consumption layers do not have this problem: they are refreshed from
bronze on every run, so a bad run is corrected by the next good one. The data volumes there
are also small enough that repeated rebuilds cost nothing meaningful.

## Decision

Deploy one Databricks Asset Bundle with two **targets** in the same workspace and metastore:

| Target | Mode | Catalog | Scope | Schedules |
|---|---|---|---|---|
| `dev` | `development` | `mls_dev` | 5 players, 1 match each, no timeline | paused automatically |
| `prod` | `production` | `mls` | 300 players, 3 matches each, timeline on | active |

`mode: development` prefixes resource names with the deploying user and pauses schedules, so
the two sets of jobs are unambiguous in the Workflows list. Scope is a bundle variable, so the
same code runs in both.

Development of harmonized and consumption logic reads from the **prod** bronze layer, because
that is where representative data lives and because rebuilding those layers is safe. The dev
target exists primarily for changes to ingestion.

## Alternatives considered

**One target, scope passed per run.** Simplest. Rejected: an accidental full-scope run writes
permanently into bronze and can exhaust the daily quota. The failure mode is both
irreversible and easy to trigger.

**Two targets writing to the same catalog.** Rejected: development ingestion output would mix
with production bronze, and because bronze is append-only, the contamination is permanent.
Deduplication would hide it rather than surface it.

**A second Databricks account for development.** Rejected: against the spirit of the free
tier, and it doubles every operational task.

## Consequences

- Two jobs appear in the workspace, `[dev <user>] ingest_and_transform_challenger` and
  `ingest_and_transform_challenger`. This is intended and visible.
- `mls_dev` holds a small amount of data most of the time and can be dropped and recreated
  freely.
- **Open risk:** Free Edition allows one active Lakeflow pipeline per type. If that means one
  pipeline *resource* rather than one *concurrent run*, the dev target cannot have its own
  pipeline. Mitigation in that case: the dev target deploys only the ingestion job and
  transformation changes are validated against `mls_dev` by running the pipeline with a
  target override. Tracked in the [validation plan](../operations/validation-plan.md).
