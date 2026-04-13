# dbx-mls — Databricks Modern Lakehouse (League of Legends)

## What This Is

A production-grade Data Engineering portfolio project that ingests League of Legends data from the Riot Games API into a Medallion Architecture (Bronze → Silver → Gold) running on **Azure Databricks with Unity Catalog**. The project demonstrates a "day in the life of a Modern Data Engineer" using **Agentic AI tooling** — Claude Code designs and builds the entire pipeline while the **ai-dev-kit MCP** gives Claude direct control over the Databricks workspace. Deployed via **Databricks Asset Bundles (DABs)** with a full **GitHub Actions CI/CD pipeline**.

## Core Value

A person can run this pipeline end-to-end in under 30 minutes and see a real, parameterized, enterprise-pattern data product — not a tutorial skeleton.

## Requirements

### Validated

**Validated in Phase 01 (infrastructure-governance-ci-cd-foundation):**
- Azure Databricks workspace with Unity Catalog enabled
- `lol_analytics` catalog with `bronze`, `silver`, `gold` schemas
- DABs with `dev` and `prod` targets, GitHub Actions CI/CD (`validate → pytest → deploy-dev` on push, manual prod on tag)
- OIDC-based SP auth (azure-cli type); `source: GIT` for notebook tasks in UC workspaces

**Validated in Phase 02 (bronze-ingestion-pipeline):**
- All 6 Bronze Delta tables defined and ingested via MERGE + anti-join patterns: `league_entries`, `match_ids`, `match_raw`, `match_timeline_raw`, `summoner_raw`, `account_raw`
- Riot API rate limiting (dual-bucket: 20 req/sec + 100 req/2min) with `Retry-After` handling
- 17-platform routing map centralised in `src/config.py` (platform vs regional host disambiguation)
- `ingestion_job.yml` — 6-task DAB DAG with correct dependency chain
- 55 unit tests passing with zero live API calls

### Active

**Infrastructure & Environment**
- [ ] Azure Databricks workspace provisioned with Unity Catalog enabled
- [ ] `lol_analytics` catalog with `bronze`, `silver`, `gold` schemas in Unity Catalog
- [ ] Databricks Asset Bundles (DABs) define all jobs, clusters, and schemas as IaC
- [ ] `dev` and `prod` DAB targets configured (environment promotion pattern)
- [ ] Riot Games API key stored securely in Databricks Secrets

**Ingestion — Bronze Layer**
- [ ] `bronze.league_entries` — raw League-Exp-V4 JSON per tier/region page
- [ ] `bronze.match_ids` — raw match ID lists per PUUID from Match-V5
- [ ] `bronze.match_raw` — full Match-V5 Detail JSON (metadata + info)
- [ ] `bronze.match_timeline_raw` — full Match-V5 Timeline JSON (frames + events)
- [ ] `bronze.summoner_raw` — Summoner-V4 profiles by PUUID
- [ ] `bronze.account_raw` — Account-V1 account details
- [ ] All Bronze tables store raw JSON as-is with ingestion metadata (`_ingested_at`, `_source`, `_region`, `_tier`)
- [ ] Region and Tier are runtime parameters — no code changes to switch from KR/Challenger to any other

**Transformation — Silver Layer**
- [ ] `silver.match` — flat match-level fields from `info` (gameId, mode, duration, version, etc.)
- [ ] `silver.match_participants` — one row per participant, all 147 fields flattened
- [ ] `silver.match_teams` — one row per team per match (teamId, win, objectives)
- [ ] `silver.match_teams_bans` — one row per ban (`bans` array exploded)
- [ ] `silver.match_teams_objectives` — one row per objective per team (pivoted from feats + objectives objects)
- [ ] `silver.match_timeline_frames` — one row per frame (timestamp, participantFrames count)
- [ ] `silver.match_timeline_participant_frames` — one row per participant per frame (championStats, damageStats, position, gold, XP)
- [ ] `silver.match_timeline_events` — one row per event per frame (event type, timestamps, involved participants)
- [ ] `silver.league_entries` — cleaned and typed League-Exp-V4 entries (tier, rank, LP, wins, losses, flags)
- [ ] All Silver tables are Delta format, schema-enforced, with full lineage columns

**Aggregation — Gold Layer**
- [ ] Gold layer definition deferred — to be scoped after Silver is validated and real data patterns are understood
- [ ] Initial candidates: champion performance aggregates, player stats trends, meta pick/ban rates, ranked tier distributions

**CI/CD & Quality**
- [ ] GitHub Actions: `validate → pytest → deploy-dev` on every push
- [ ] GitHub Actions: `manual approval → deploy-prod` on release tags only
- [ ] `databricks bundle validate` catches config/YAML errors before any deploy
- [ ] Unit tests (pytest) cover transformation logic — no Databricks runtime required
- [ ] Integration tests run against `dev` environment post-deploy

**Agentic Showcase**
- [ ] ai-dev-kit MCP configured so Claude can interact directly with the workspace, this should be featured in the text deliverable explained below
- [ ] Each phase produces a LinkedIn deliverable: detailed article version + short post version

### Out of Scope

- **Other queue types** (ARAM, Arena, TFT) — focus on RANKED_SOLO_5x5 only for v1; architecture supports extension
- **Real-time / streaming** — batch ingestion only for v1; streaming via Delta Live Tables is a future milestone
- **Jira / team simulation integration** — explicitly planned for a future milestone, not v1
- **Gold layer detailed design** — intentionally deferred until Silver data patterns are validated
- **Multi-region/tier simultaneous ingestion** — start with KR/Challenger+Grandmaster, parameters make region/tier switching trivial without parallel support

## Context

**Why this project exists:** Career advancement portfolio targeting senior/staff Data Engineering roles. The Agentic AI angle (Claude Code + MCP) differentiates it from standard tutorial projects — it shows the candidate understands where tooling is heading.

**Riot Games API specifics (from schema_report.md):**
- 6 endpoint families covered; Match-V5 is the richest with 147 participant fields + timeline frames
- Participant object has nested arrays/objects: `challenges` (125 fields), `perks`, `missions`, `PlayerBehavior`
- Timeline has `frames[]` → `participantFrames{}` → `championStats`, `damageStats`, `position` (all nested)
- League-Exp-V4 returns ~200 entries per tier/page — the seeding endpoint for the player pipeline
- Match-V5 uses routing values (`americas`, `europe`, `asia`, `sea`) separate from platform (`KR`, `NA1`, etc.)

**Developer environment:** Linux Mint, Azure CLI, Databricks CLI, Python 3.x, DABs

**Riot API Key:** Development key (24h expiry). Production key registration to be documented in Phase 1 setup.

**Initial demo configuration:** Korea (`KR`) server, Challenger + Grandmaster tiers — highest quality match data, good for showcasing analytics depth.

## Constraints

- **API Rate Limits**: Riot Dev key — 20 req/sec, 100 req/2min. Pipeline must include rate limit handling and backoff logic.
- **Secrets Management**: API keys and workspace tokens must never be hardcoded — Databricks Secrets only.
- **Unity Catalog**: All tables must be three-part names (`lol_analytics.{layer}.{table}`) — no `hive_metastore`.
- **Code Quality**: Enterprise-ready standard — modular, documented, no magic strings, config-driven parameters.
- **Parameterization**: Region and Tier are always runtime parameters (DAB job parameters), never hardcoded constants.
- **LinkedIn cadence**: One phase = one post pair (detailed article + short summary). Posts must be written before phase is considered complete.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Azure over AWS | Easier Databricks onboarding, dominant in enterprise DE, strongest portfolio signal for target market | — Pending |
| Unity Catalog only (no Hive Metastore) | Industry is fully migrating to UC; hiring managers expect UC fluency | — Pending |
| DABs over Terraform for IaC | Native Databricks IaC, lower overhead, directly maps to DE workflows vs platform/infra roles | — Pending |
| `lol_analytics` as catalog name | Describes the business domain, not the infrastructure — follows industry standard product naming | — Pending |
| Silver: one table per array | Avoids complex struct queries in SQL, enables clean joins, aligns with enterprise data warehouse patterns | — Pending |
| Gold: deferred | Avoid premature optimization — design Gold around real Silver data patterns, not assumptions | — Pending |
| KR Challenger/Grandmaster as demo target | Highest match quality, showcases pipeline capability on complex data | — Pending |
| CI/CD: validate→test→deploy-dev on push, prod on tag | Demonstrates GitFlow, test pyramid, and environment promotion — maximizes hiring signal | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-13 — Phase 02 bronze-ingestion-pipeline complete*
