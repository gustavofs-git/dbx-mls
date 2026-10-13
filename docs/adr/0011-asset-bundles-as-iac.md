# ADR-0011 — Databricks Asset Bundles as the only deployment mechanism

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

Jobs, pipelines, schemas and volumes must be reproducible from the repository. Free Edition
accounts may be deleted after inactivity, so "recreate everything from scratch" is a real
recovery scenario, not a hypothetical.

Databricks Asset Bundles describe workspace resources in YAML (`databricks.yml` plus
`resources/*.yml`), synchronize code into the workspace, and create or update resources
through the API. Internally they are Terraform, specialized for Databricks.

## Decision

Every workspace resource is declared in the bundle, and `databricks bundle deploy` is the only
way anything reaches the workspace. Nothing is created by clicking in the UI.

```
databricks.yml              targets, variables, workspace host
resources/
├── jobs.yml                ingest_and_transform_challenger, maintain_storage
├── pipelines.yml           transform_lol_medallion
└── schemas.yml             catalogs, schemas, volumes
conf/ingestion_scope.yml    scope, overridden per target
```

Scope values that differ between targets — `max_players`, `matches_per_player`,
`include_timeline`, `catalog_name` — are bundle variables, so one codebase serves both
targets.

## Alternatives considered

**Terraform with the Databricks provider.** More general, and transferable across clouds.
Rejected: it duplicates what bundles already wrap, requires state management that Free Edition
has nowhere good to store, and adds a toolchain for no capability gain here.

**Notebooks deployed by hand, jobs configured in the UI.** Rejected outright: not
reproducible, not reviewable, and it would make the recovery scenario a memory exercise.

**Databricks CLI scripting against the Jobs API directly.** Rejected: imperative create-or-
update logic written by hand is exactly what the bundle does correctly, including deletion of
resources removed from the definition.

## Consequences

- The entire platform is recreated with `databricks bundle deploy -t prod` after an account
  loss, provided secrets are re-created — which is a documented runbook step.
- Resource changes go through pull request review like code, and `bundle validate` catches
  malformed definitions in CI before anything is deployed.
- Any resource created manually in the UI is outside the system of record and will be
  overwritten or orphaned. The runbook states this explicitly.
- Bundle semantics must be learned, including `mode: development` behaviour, which is
  documented in [ADR-0002](0002-single-workspace-two-bundle-targets.md).
