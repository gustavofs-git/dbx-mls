# Phase 1 LinkedIn Post

I pushed to main. Databricks deployed. No tokens. No PATs. No secrets in GitHub. Just OIDC.

That is Phase 1 of dbx-mls — a production Databricks Lakehouse portfolio built to show real enterprise DE patterns.

What shipped:

- **OIDC Workload Identity Federation** — GitHub Actions authenticates via a short-lived OIDC token. Two federation policies: branch-scoped for dev CI, environment-scoped with an approval gate for prod. Zero stored credentials.

- **Databricks Asset Bundles (DABs)** — Every job, cluster, and schema declared as YAML. Dev and prod targets in one bundle. Prod target uses `run_as` with a Service Principal so production never runs as a human identity.

- **Unity Catalog SP ownership from CI** — Schema ownership is set on first deploy. The bootstrap SQL grants ensure the SP owns all schemas from day one — not a developer's laptop.

- **Permanent smoke test** — Three validations on every dev deploy: API key retrievable (redacted in logs), UC schemas accessible, Bronze table roundtrip. CI is green only if the workspace is healthy.

Full walkthrough — OIDC federation setup, real `databricks.yml` YAML, UC grant SQL — in the article below.

Repo: `<github-repo-url>`
