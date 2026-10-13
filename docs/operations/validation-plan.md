# Feasibility validation plan

The governing rule of this project: **no platform capability is assumed.** Anything not
confirmed by documentation is proven by a probe against the workspace before code depends on
it.

Each probe is small, runs in minutes, and has a defined fallback. They are executed in
Epic 0 — see the [roadmap](../project/roadmap.md) — and re-run by the `dbx-validator`
subagent whenever a platform assumption is questioned.

## Blocking probes

These gate design decisions already recorded. A failure supersedes an ADR.

| # | Question | Method | Fallback if it fails | Gates |
|---|---|---|---|---|
| V1 | Does the CLI authenticate to Free Edition with a PAT? | `databricks auth login`, then `databricks current-user me` | none — the project is not viable without it | everything |
| V2 | Can a bundle be deployed with a PAT? | deploy a bundle containing one trivial job to `dev` | manual deployment, documented as a limitation | [ADR-0011](../adr/0011-asset-bundles-as-iac.md), [ADR-0012](../adr/0012-cicd-github-actions-pat.md) |
| V3 | Does `VARIANT` work on serverless compute? | `CREATE TABLE … (payload VARIANT)`, insert one real match payload, query `payload:info.gameVersion::string` | `payload STRING` + `get_json_object`; supersede ADR-0004 | [ADR-0004](../adr/0004-raw-payload-as-variant.md) |
| V4 | Does `VARIANT` work inside a Lakeflow declarative pipeline? | one-table pipeline reading the V3 table | as V3 | [ADR-0004](../adr/0004-raw-payload-as-variant.md), [ADR-0007](../adr/0007-declarative-pipeline-imperative-ingestion.md) |
| V5 | Does a 5 MB timeline payload fit in a `VARIANT` value? | insert the largest timeline available; confirm no truncation | timelines as `STRING`, match detail as `VARIANT` | [ADR-0004](../adr/0004-raw-payload-as-variant.md) |
| V6 | Can two catalogs be created? | `CREATE CATALOG mls`, `CREATE CATALOG mls_dev` | one catalog, `*_dev` schema suffixes | [ADR-0002](../adr/0002-single-workspace-two-bundle-targets.md) |
| V7 | Can a secret scope be created via CLI? | `databricks secrets create-scope mls`, put and read a key | job environment variables declared in the bundle, documented as weaker | [ADR-0010](../adr/0010-puuid-pseudonymization.md) |
| V8 | "One active pipeline per type" — one resource, or one concurrent run? | deploy a pipeline to both targets; observe | dev validates transformations by running the prod pipeline against the dev catalog | [ADR-0002](../adr/0002-single-workspace-two-bundle-targets.md), [ADR-0007](../adr/0007-declarative-pipeline-imperative-ingestion.md) |
| V9 | Does the workspace reach `api.riotgames.com`? | `requests.get` from a serverless notebook | the project is not viable; re-scope to a reachable source | [ADR-0003](../adr/0003-data-source-scope-kr-challenger.md) |
| V10 | Does Auto Loader work against a UC volume on serverless? | land three files, stream them into a table | batch read of the volume with manual high-water marking | [ADR-0005](../adr/0005-landing-zone-before-bronze.md) |

## Non-blocking probes

These affect optional features. A failure is recorded as a platform limitation.

| # | Question | Method | If it fails |
|---|---|---|---|
| V11 | Does `VARIANT` exist in open-source PySpark? | `pytest` locally against a `VARIANT` expression | `VARIANT` navigation stays confined to `transforms/extract.py`; that module is covered by integration tests only |
| V12 | Are SQL AI functions available? | `SELECT ai_gen('hello')` on the warehouse | the weekly natural-language summary is dropped; recorded in [ADR-0016](../adr/0016-ai-usage-scope.md) |
| V13 | Are metric views available? | create one over `harmonized.match_participants` | the consumption layer stays as plain SQL views |
| V14 | Does `databricks-sql-connector` work with a PAT against the 2X-Small warehouse? | query one row from GitHub Actions | the public showcase export needs a different mechanism |
| V15 | Can a Databricks dashboard be shared externally? | attempt to publish one | screenshots and video only |
| V16 | Is a service principal available? | look for account-level APIs | confirms the PAT deviation in [ADR-0012](../adr/0012-cicd-github-actions-pat.md) |
| V17 | Is there a documented storage quota? | check account settings and documentation | plan conservatively and monitor `ops.dq_metrics` volumetry |

## Recording results

Probe results are recorded in this page as a table appended below, with the date and the
outcome. A probe that changes a decision triggers a superseding ADR in the same pull request.

| Probe | Date | Result | Action taken |
|---|---|---|---|
| _(pending Epic 0)_ | | | |
