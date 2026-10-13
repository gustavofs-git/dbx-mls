# ADR-0001 — Build on Databricks Free Edition and design around its limits

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The project must cost nothing and must still resemble a professional Databricks delivery.
Databricks Free Edition provides Unity Catalog, serverless compute, Lakeflow declarative
pipelines, Jobs, a SQL warehouse and Asset Bundle deployment at no cost, which is a closer
match to a real engagement than any local Spark setup.

Its documented constraints shape the whole design:

| Constraint | Consequence for this project |
|---|---|
| serverless compute only | no cluster configuration to demonstrate; no Scala or R |
| one workspace, one metastore, no account console | no account-level APIs, no SSO, no service principal (to be verified) |
| one SQL warehouse (2X-Small) | consumption-layer queries must be cheap; materialization must be justified |
| max 5 concurrent job tasks | no wide fan-out orchestration |
| one active Lakeflow pipeline per type | dev and prod pipelines may not be able to coexist — see [ADR-0002](0002-single-workspace-two-bundle-targets.md) |
| Databricks-managed storage only; no S3/ADLS/GCS | no external location or storage credential patterns |
| no documented storage quota, but usage quotas exist | exceeding a quota disables compute until the next day |
| inactive accounts may be deleted | the repository must reconstruct everything, and a job must run regularly |
| non-commercial use | presented as a personal project |

## Decision

Build on Free Edition, and treat every constraint as an explicit design input that is
documented rather than worked around silently.

Two operating rules follow:

1. **No capability is assumed.** Anything not confirmed by documentation is proven by a probe
   against the workspace before code depends on it. See the
   [validation plan](../operations/validation-plan.md).
2. **The repository is the source of truth.** Catalogs, schemas, volumes, jobs and pipelines
   are all declared in the bundle, so the entire platform can be recreated in one command
   after an account loss.

## Alternatives considered

**Databricks trial on a cloud provider.** Full feature set, including service principals and
external storage. Rejected: it expires, and the underlying cloud storage and compute are not
free. A portfolio project that dies after 14 days is worse than one with documented limits.

**Local Spark, or Spark in Docker.** Free and unlimited. Rejected: Unity Catalog, Lakeflow
pipelines, Jobs and Asset Bundles are the specific skills being demonstrated, and none of them
exist locally. The limitation would be invisible to a reader but total.

**A different managed free tier (Snowflake trial, BigQuery sandbox, Microsoft Fabric trial).**
Rejected: the target skill set is Databricks.

## Consequences

- Several design decisions in this repository are correct *here* and would be wrong in a
  production environment with a budget. Each one says so in its own record.
- The credential model is a personal access token rather than a service principal with OAuth
  M2M. This is a documented deviation, not a recommendation; see
  [ADR-0012](0012-cicd-github-actions-pat.md).
- Quota exhaustion is a real operational risk during development, which is why the dev target
  runs with a deliberately tiny scope.
- The project gains a genuine engineering theme — delivering within hard resource limits —
  that an unconstrained environment would not have produced.
