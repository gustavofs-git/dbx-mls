# Decision records

Architectural decisions are recorded in [MADR](https://adr.github.io/madr/) format: context,
decision, alternatives considered, consequences. Each record states what was rejected and
why, because the rejected option is usually the more informative half.

A record is never edited to reflect a change of mind. It is superseded by a new record, and
the old one is marked. The history of the reasoning is the point.

| # | Decision | Status |
|---|---|---|
| [0001](0001-platform-databricks-free-edition.md) | Build on Databricks Free Edition and design around its limits | Accepted |
| [0002](0002-single-workspace-two-bundle-targets.md) | One workspace, two bundle targets, catalog per target | Accepted |
| [0003](0003-data-source-scope-kr-challenger.md) | Scope: KR Challenger solo queue, match detail and timeline | Accepted |
| [0004](0004-raw-payload-as-variant.md) | Store the raw API payload as `VARIANT` | Accepted, pending validation |
| [0005](0005-landing-zone-before-bronze.md) | Land raw responses as files before writing bronze | Accepted |
| [0006](0006-two-physical-layers-virtual-consumption.md) | Two physical layers, virtual consumption layer | Accepted |
| [0007](0007-declarative-pipeline-imperative-ingestion.md) | Declarative pipeline for transformation, imperative job for ingestion | Accepted |
| [0008](0008-data-quality-strategy.md) | Drop impossible values, keep valid-but-out-of-scope records | Accepted |
| [0009](0009-native-expectations-over-external-dq.md) | Native pipeline expectations rather than Great Expectations or Soda | Accepted |
| [0010](0010-puuid-pseudonymization.md) | Pseudonymize `puuid` with HMAC at the harmonized boundary | Accepted |
| [0011](0011-asset-bundles-as-iac.md) | Databricks Asset Bundles as the only deployment mechanism | Accepted |
| [0012](0012-cicd-github-actions-pat.md) | GitHub Actions; CI does not write to the workspace on pull requests | Accepted |
| [0013](0013-docs-as-code-mkdocs.md) | Documentation as code, published with MkDocs Material | Accepted |
| [0014](0014-weekly-cadence-daily-maintenance.md) | Weekly ingestion, daily maintenance job | Accepted |
| [0015](0015-timeline-event-type-filtering.md) | Filter timeline events to four types at the harmonized layer | Accepted |
| [0016](0016-ai-usage-scope.md) | AI in the development process; in-pipeline AI optional; no ML in v1 | Accepted |
| [0017](0017-single-article-over-post-series.md) | One long-form article instead of a series of posts | Accepted |
