# mylolstats

**A data platform on Databricks Free Edition that turns Riot Games match data into high-elo
meta analytics — and argues that the third medallion layer should be earned, not assumed.**

[![docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://gustavofs-git.github.io/dbx-mls/)

> 📖 **[Full documentation](https://gustavofs-git.github.io/dbx-mls/)** — architecture, data
> model, decision records, runbook.

---

## The question

> What does the meta look like at the very top of the Korean ladder, and how does it move
> between patches?

KR Challenger is the leading indicator of the global League of Legends meta. The platform
answers, per patch and per lane: which champions are picked, banned and won with; how gold
and experience diverge by minute 15; and which objectives correlate with victory.

## The thesis

Most data engineering portfolios implement three materialized medallion layers because that
is the convention. This one does not, and the reasoning is the point:

| | Textbook medallion | This project |
|---|---|---|
| Raw payload | parsed into typed columns, or JSON as `STRING` | **`VARIANT`** — schema-free, shredded, queryable |
| Physical layers | 3 | **2** — bronze, harmonized |
| Dimensional model | materialized gold tables | **views** over harmonized |
| Justification | convention | measured: 78k fact rows do not justify materialization |

The dimensional model still exists, with stated grain and stated denominators. It simply
costs no storage and no pipeline. Materialization becomes a decision earned by a measured
requirement — and a `CREATE TABLE AS SELECT` away when one appears.

Full argument, including the case against:
**[ADR-0006](https://gustavofs-git.github.io/dbx-mls/adr/0006-two-physical-layers-virtual-consumption/)**

## Architecture

```mermaid
flowchart LR
    API["Riot API<br/>league-v4 · match-v5"]
    LDZ["Landing zone<br/><i>Volume · raw JSON.gz</i>"]
    BR["bronze<br/><i>payload VARIANT</i>"]
    HM["harmonized<br/><i>typed · deduped · validated</i>"]
    CS["consumption<br/><i>dim_* fct_* agg_* — views</i>"]

    API -->|"Python job<br/>rate limit · retry · backoff"| LDZ
    LDZ -->|Auto Loader| BR
    BR -->|"declarative pipeline<br/>+ expectations"| HM
    HM --> CS
```

Ingestion is imperative because throttled HTTP I/O is; everything after the landing zone is
a declarative pipeline because table definitions with dependencies are.

## Stack

| | |
|---|---|
| Platform | Databricks Free Edition — serverless, Unity Catalog, Lakeflow declarative pipelines |
| Language | Python 3.12, PySpark |
| IaC | Databricks Asset Bundles |
| CI/CD | GitHub Actions — ruff, pytest, `bundle validate`, deploy |
| Data quality | native pipeline expectations, measured into `ops.dq_metrics` |
| Docs | MkDocs Material on GitHub Pages; decisions as MADR records |

## Engineering notes

- **Resilience as a feature.** The Riot development key expires every 24 hours. A run that
  finds an invalid credential exits as a recorded *skip*, not a failure — credential
  availability is an expected input condition, not an incident.
- **Privacy by construction.** `puuid` never crosses into the harmonized layer. It becomes
  `HMAC-SHA256(puuid, salt)`, with the salt in a secret scope. A plain hash of an enumerable
  identifier space would be reversible, so it is not used.
- **Quality separated from scope.** Impossible values (`kills = -1`) are dropped and counted.
  True-but-out-of-scope records (remakes, ARAM) are kept as attributes and filtered in four
  view definitions, because analytical scope is the thing most likely to change.
- **Nothing is assumed about the platform.** Seventeen capability probes gate the design, each
  with a defined fallback. Several ADRs are explicitly conditional on them.
- **Built with agents, documented as such.** The `CLAUDE.md`, five skills and one validation
  subagent are versioned here, along with what was delegated and what was reviewed by hand.

## Reproducing it

```bash
uv sync && uv run pre-commit install
databricks auth login --host https://<workspace>.cloud.databricks.com
databricks secrets create-scope mls
databricks secrets put-secret mls riot_api_key
databricks secrets put-secret mls pseudonym_salt
databricks bundle deploy -t prod
```

Detailed procedure, including recovery from account loss:
**[runbook](https://gustavofs-git.github.io/dbx-mls/operations/runbook/)**

## Living within the free tier

Free Edition disables compute for the rest of the day when a quota is exceeded. The design
budget is roughly **300 MB of compressed Delta per weekly run**:

- scope is configuration, not code — the dev target runs 5 players instead of 300
- CI never writes to the workspace on a pull request
- the consumption layer materializes nothing
- a daily maintenance job runs `OPTIMIZE`, `VACUUM` and retention — and keeps the account
  from being deleted for inactivity

See [quotas and retention](https://gustavofs-git.github.io/dbx-mls/operations/quotas-and-retention/).

## Status

Design complete and recorded as 17 decision records. Implementation begins at Epic 0 —
feasibility probes — in the
[roadmap](https://gustavofs-git.github.io/dbx-mls/project/roadmap/).

---

Personal, non-commercial project. Not affiliated with or endorsed by Riot Games. Published
output is aggregated and contains no player identifiers.
