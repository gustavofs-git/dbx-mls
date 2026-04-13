# Requirements: dbx-mls — Databricks Modern Lakehouse (League of Legends)

**Defined:** 2026-04-07
**Core Value:** A recruiter or hiring manager can run this pipeline end-to-end in under 30 minutes and see a real, parameterized, enterprise-pattern data product — not a tutorial skeleton.

## v1 Requirements

### Infrastructure & Governance (INFRA)

- [x] **INFRA-01**: Azure Databricks workspace provisioned with Unity Catalog enabled
- [x] **INFRA-02**: `lol_analytics` catalog created with `bronze`, `silver`, and `gold` schemas in Unity Catalog
- [x] **INFRA-03**: Service Principal created, assigned schema ownership from CI (not developer laptop) — prevents ownership lock-in
- [x] **INFRA-04**: Databricks Asset Bundles `databricks.yml` defines `dev` and `prod` targets with DBR 16.4 LTS cluster config
- [x] **INFRA-05**: Riot API key stored in Databricks Secret Scope (`secrets/riot-api/key`) — never hardcoded
- [x] **INFRA-06**: Smoke-test DAB deploy succeeds end-to-end before any pipeline code is written
- [x] **INFRA-07**: `.gitignore` excludes all secrets, `.env` files, and Python artifacts

### CI/CD Pipeline (CICD)

- [x] **CICD-01**: GitHub Actions `ci.yml` — runs `databricks bundle validate` + `pytest` on every push to any branch
- [x] **CICD-02**: GitHub Actions `cd-dev.yml` — deploys bundle to `dev` target on every push to `main`
- [x] **CICD-03**: GitHub Actions `cd-prod.yml` — deploys bundle to `prod` target only on release tags (`v*`), with manual approval gate via GitHub Environment protection
- [x] **CICD-04**: Authentication uses OIDC federation (Workload Identity) — zero long-lived secrets in GitHub
- [x] **CICD-05**: `setup-databricks-cli` action pins Databricks CLI version (`>=0.250.0`)
- [x] **CICD-06**: Prod deploy job is in a separate workflow with `concurrency` group to prevent parallel prod deploys

### Bronze Ingestion (BRZ)

- [x] **BRZ-01**: `RiotApiClient` class in `src/riot_client.py` with dual-bucket rate limiter (20 req/sec + 100 req/2min) and `Retry-After` header parsing
- [x] **BRZ-02**: Region and Tier are DAB job parameters (`region`, `tier`) — never hardcoded; KR/CHALLENGER is the default value only
- [x] **BRZ-03**: Platform-to-routing-host mapping config (`KR` → `asia`, `NA1` → `americas`, etc.) in `src/config.py` — covers all 17 Riot platforms
- [x] **BRZ-04**: `bronze.league_entries` table populated from League-Exp-V4 (paginated until empty page), raw JSON as STRING with `_ingested_at`, `_source_url`, `_region`, `_tier` metadata columns
- [x] **BRZ-05**: `bronze.match_ids` table populated from Match-V5 `/by-puuid/{puuid}/ids`, with MERGE deduplication on `(puuid, match_id)` — no re-fetching already-ingested IDs
- [x] **BRZ-06**: `bronze.match_raw` table populated from Match-V5 `/matches/{matchId}`, with MERGE deduplication on `match_id` — full JSON as STRING
- [ ] **BRZ-07**: `bronze.match_timeline_raw` table populated from Match-V5 `/matches/{matchId}/timeline`, separately from match detail (distinct DAB task, independent rate limit budget)
- [ ] **BRZ-08**: `bronze.summoner_raw` table populated from Summoner-V4 by PUUID (enrichment, non-blocking)
- [ ] **BRZ-09**: `bronze.account_raw` table populated from Account-V1 by PUUID (enrichment, non-blocking)
- [x] **BRZ-10**: All Bronze tables are Delta format, UC three-part names (`lol_analytics.bronze.*`), no DBFS paths, no Hive Metastore

### Silver Transformation (SLV)

- [ ] **SLV-01**: `schemas/match_schema.py` defines all Silver StructType schemas as version-controlled Python constants — built from real Bronze response, not inferred
- [ ] **SLV-02**: `silver.match` — flat match-level fields from `info` (gameId, mode, duration, version, platformId, queueId, gameCreation, etc.)
- [ ] **SLV-03**: `silver.match_participants` — one row per participant per match, all 147 fields flattened, `challenges` struct flattened to `chal_*` prefix columns (125 fields), `perks` and `missions` flattened
- [ ] **SLV-04**: `silver.match_teams` — one row per team per match (teamId, win, feats)
- [ ] **SLV-05**: `silver.match_teams_bans` — `bans[]` array exploded, one row per ban (championId, pickTurn, match_id, teamId)
- [ ] **SLV-06**: `silver.match_teams_objectives` — objectives struct pivoted to rows (objectiveType, first, kills, match_id, teamId)
- [ ] **SLV-07**: `silver.match_timeline_frames` — one row per frame (timestamp, match_id)
- [ ] **SLV-08**: `silver.match_timeline_participant_frames` — one row per participant per frame (championStats 25 fields + damageStats 12 fields + position + gold + XP)
- [ ] **SLV-09**: `silver.match_timeline_events` — one row per event per frame (event type, realTimestamp, timestamp, match_id, frame_index)
- [ ] **SLV-10**: `silver.league_entries` — cleaned and typed League-Exp-V4 entries (tier, rank, LP, wins, losses, boolean flags, computed win_rate)
- [ ] **SLV-11**: All Silver writes use MERGE WITH SCHEMA EVOLUTION (idempotent, handles new Riot API fields additively)
- [ ] **SLV-12**: All Silver tables use Liquid Clustering (not partition-by) on the most selective query key per table
- [ ] **SLV-13**: Silver transformation functions are pure Python (DataFrame in → DataFrame out) enabling local unit tests without a live cluster

### Testing (TEST)

- [ ] **TEST-01**: Unit tests for all Silver transformation functions using `pyspark` local mode + `chispa` DataFrame assertions
- [ ] **TEST-02**: Unit tests for `RiotApiClient` rate limiter logic (mocked HTTP responses)
- [ ] **TEST-03**: Unit tests for schema definitions (field count, type assertions)
- [ ] **TEST-04**: `pytest` runs locally on Linux without a live Databricks cluster (Java 11 installed, `JAVA_HOME` set)
- [ ] **TEST-05**: Test coverage report generated on CI runs

### Gold & Analytics (GOLD)

- [ ] **GOLD-01**: `gold.champion_performance` — aggregated stats per champion (avg KDA, win rate, avg damage dealt, avg CS, games played) filterable by region/tier/patch
- [ ] **GOLD-02**: `gold.pick_ban_rates` — pick rate and ban rate per champion per patch, computed from `silver.match_participants` and `silver.match_teams_bans`
- [ ] **GOLD-03**: `gold.tier_distribution` — count of players and average LP per tier/rank division from `silver.league_entries`
- [ ] **GOLD-04**: Gold tables are read-only views or Delta tables created from Silver — never read from Bronze directly

### Agentic Showcase & Portfolio (AGTC)

- [ ] **AGTC-01**: `ai-dev-kit` MCP configured locally so Claude can interact with the workspace via MCP tools (list tables, run jobs, query data)
- [ ] **AGTC-02**: `README.md` includes architecture diagram, quickstart steps (< 30 min to running), and "How Claude built this" section
- [ ] **AGTC-03**: `Makefile` provides `make setup`, `make test`, `make deploy-dev`, `make deploy-prod` targets
- [x] **AGTC-04**: Each phase produces a LinkedIn post pair: detailed article version + short summary version (committed to `docs/posts/`)

## v2 Requirements

### Streaming & Real-time (STRM)

- **STRM-01**: Delta Live Tables pipeline replaces batch Bronze jobs for near-real-time ingestion
- **STRM-02**: Auto Loader monitors a cloud storage landing zone for new match export files

### Extended Coverage (EXT)

- **EXT-01**: Multi-region ingestion (NA1, EUW1, BR1) running in parallel DAB tasks
- **EXT-02**: All queue types supported (ARAM, Arena, TFT) with queue-specific Silver schemas
- **EXT-03**: Jira integration — Claude simulates full team workflow (ticket creation, sprint tracking, review cycle)

### Monitoring & Observability (OBS)

- **OBS-01**: Databricks job alerts on failure with Slack/email notification
- **OBS-02**: Data quality expectations (Delta Expectations / Great Expectations) on Silver tables
- **OBS-03**: Row count trend dashboard in Databricks SQL

### Champion & Item Metadata (META)

- **META-01**: Data Dragon API (static champion/item data) ingested and joined into Silver/Gold for human-readable names
- **META-02**: Patch version tracked across matches for temporal analysis

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time streaming (v1) | High complexity, batch ingestion is sufficient for portfolio demo; deferred to v2 |
| ARAM / Arena / TFT queues | Requires different Silver schemas; scope focused on RANKED_SOLO_5x5 for v1 |
| Multi-region parallel ingestion | Region is a parameter; simultaneous multi-region is v2 complexity |
| Hive Metastore | Databricks is fully migrating to Unity Catalog; HC is a career anti-pattern to demonstrate |
| DBFS mounts (`dbfs:/mnt/`) | Incompatible with Unity Catalog clusters; all data via UC tables or Volumes |
| Terraform workspace provisioning | DABs deploy assets only; workspace provisioning documented as manual prerequisite |
| OpenAI or other AI providers | AI tooling showcase is specifically Claude Code + MCP ai-dev-kit |
| Gold layer designed before Silver | Explicitly deferred — Gold design should be informed by real Silver data patterns |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| INFRA-06 | Phase 1 | Complete |
| INFRA-07 | Phase 1 | Complete |
| CICD-01 | Phase 1 | Complete |
| CICD-02 | Phase 1 | Complete |
| CICD-03 | Phase 1 | Complete |
| CICD-04 | Phase 1 | Complete |
| CICD-05 | Phase 1 | Complete |
| CICD-06 | Phase 1 | Complete |
| BRZ-01 | Phase 2 | Complete |
| BRZ-02 | Phase 2 | Complete |
| BRZ-03 | Phase 2 | Complete |
| BRZ-04 | Phase 2 | Complete |
| BRZ-05 | Phase 2 | Complete |
| BRZ-06 | Phase 2 | Complete |
| BRZ-07 | Phase 2 | Pending |
| BRZ-08 | Phase 2 | Pending |
| BRZ-09 | Phase 2 | Pending |
| BRZ-10 | Phase 2 | Complete |
| TEST-02 | Phase 2 | Pending |
| TEST-04 | Phase 2 | Pending |
| SLV-01 | Phase 3 | Pending |
| SLV-02 | Phase 3 | Pending |
| SLV-03 | Phase 3 | Pending |
| SLV-04 | Phase 3 | Pending |
| SLV-05 | Phase 3 | Pending |
| SLV-06 | Phase 3 | Pending |
| SLV-07 | Phase 3 | Pending |
| SLV-08 | Phase 3 | Pending |
| SLV-09 | Phase 3 | Pending |
| SLV-10 | Phase 3 | Pending |
| SLV-11 | Phase 3 | Pending |
| SLV-12 | Phase 3 | Pending |
| SLV-13 | Phase 3 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-05 | Phase 3 | Pending |
| GOLD-01 | Phase 4 | Pending |
| GOLD-02 | Phase 4 | Pending |
| GOLD-03 | Phase 4 | Pending |
| GOLD-04 | Phase 4 | Pending |
| AGTC-01 | Phase 5 | Pending |
| AGTC-02 | Phase 5 | Pending |
| AGTC-03 | Phase 5 | Pending |
| AGTC-04 | Phase 1–5 | Complete |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after initial definition*
