# Naming conventions

All identifiers are English and `snake_case`. Conversation about the project may be in any
language; the artifact is in one.

## Catalogs, schemas, volumes

| Object | Convention | Value |
|---|---|---|
| catalog | one per bundle target | `mls` (prod), `mls_dev` (dev) |
| schema | the layer, not the source | `landing`, `bronze`, `harmonized`, `consumption`, `ops` |
| volume | `raw_<source>` | `landing.raw_riot` |
| landing path | `/<endpoint>/dt=<yyyy-mm-dd>/<natural_key>.json.gz` | partitioned by ingestion date |

Catalog-per-target rather than schema suffixes: permissions, retention and `DROP` operations
then apply to a whole target at once, and a fully-qualified name says which target it belongs
to without the reader having to parse a suffix.

## Tables

| Layer | Pattern | Examples |
|---|---|---|
| `bronze` | `<source>_<endpoint_entity>` — mirrors the origin, never the business | `riot_matches`, `riot_match_timelines`, `riot_league_entries` |
| `harmonized` | business entity, plural, grain explicit when ambiguous | `matches`, `match_participants`, `match_teams`, `participant_frames`, `timeline_events`, `league_entries` |
| `consumption` | `dim_` / `fct_` / `agg_` by object type | `dim_champion`, `fct_match_participant`, `agg_champion_by_patch` |
| `ops` | `<subject>_<kind>` | `dq_metrics` |

No layer prefix on table names (`br_`, `slv_`): the schema already states the layer, and
repeating it produces `mls.bronze.br_riot_matches`. The `dim_`/`fct_`/`agg_` prefixes are
different in kind — they state the *object type* within a layer, which the schema does not.

## Columns

| Rule | Example |
|---|---|
| `snake_case`, English | `champion_name`, `team_position` |
| timestamps end in `_at` | `ingested_at`, `game_started_at` |
| dates end in `_date` | `game_date`, `snapshot_date` |
| natural keys end in `_id` | `match_id`, `champion_id` |
| surrogate or pseudonymous keys end in `_sk` | `player_sk` |
| booleans start with `is_` or `has_` | `is_win`, `has_first_blood` |
| durations carry the unit | `game_duration_seconds`, `freshness_hours` |
| aggregates carry the aggregator | `avg_kda`, `total_matches`, `win_rate_pct` |
| percentages end in `_pct` and are 0–100 | `win_rate_pct` |
| audit columns are prefixed `meta_` and placed last | `meta_ingested_at`, `meta_source_file` |

The `meta_` prefix is the convention with the highest day-to-day value: it makes the boundary
between business content and ingestion trail visible without consulting documentation.

Riot's API field names are `camelCase` and are **renamed, not preserved**, at the harmonized
boundary. `teamPosition` becomes `team_position`. The original spelling remains available in
bronze.

## Jobs, pipelines, bundle

| Object | Convention | Values |
|---|---|---|
| job | `<verb>_<object>`, short; detail goes in `description` | `ingest_and_transform_challenger`, `maintain_storage` |
| task | `<verb>_<object>` | `fetch_riot_challenger`, `transform_medallion` |
| pipeline | `transform_<domain>_<scope>` | `transform_lol_medallion` |
| bundle variable | `snake_case` | `max_players`, `catalog_name` |
| secret scope / key | project name / purpose | scope `mls`, keys `riot_api_key`, `pseudonym_salt` |

Short job names with rich `description` fields rather than self-describing names: the name is
what appears in alert emails, run histories and log lines, where brevity is a feature. Every
job and task carries a `description` in the bundle YAML, which Databricks surfaces in the UI.

## Python

| Object | Convention | Example |
|---|---|---|
| package | `mls` | `src/mls/` |
| module | `snake_case`, singular | `client.py`, `pseudonymize.py` |
| class | `PascalCase`; transforms end in `Transform`, ingestors in `Ingestor` | `MatchParticipantsTransform`, `MatchV5Ingestor` |
| abstract base | prefixed `Base` | `BaseBronzeToHarmonized` |
| pure function | verb phrase | `explode_participants`, `derive_patch` |
| constant | `UPPER_SNAKE_CASE` | `HARMONIZED_TRANSFORMS` |
| test | `test_<module>.py`, `test_<behaviour>` | `test_matches.py::test_drops_negative_kills` |

## Git

| Object | Convention | Example |
|---|---|---|
| branch | `<type>/<issue>-<slug>` | `feat/42-harmonized-match-participants` |
| branch types | `feat`, `fix`, `docs`, `chore`, `refactor`, `test` | |
| commit | Conventional Commits with a layer or component scope | `feat(harmonized): add match_participants transform` |
| pull request | imperative title + `Closes #<n>` in the body | |
| ADR file | `NNNN-kebab-case-title.md`, zero-padded | `0004-raw-payload-as-variant.md` |

Commit scopes are drawn from a fixed list so history is greppable: `landing`, `bronze`,
`harmonized`, `consumption`, `ops`, `ingest`, `riot`, `bundle`, `ci`, `docs`, `tests`.
