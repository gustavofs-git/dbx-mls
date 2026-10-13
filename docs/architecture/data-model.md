# Data model

## Grain summary

"Grain" is what exactly one row represents. Getting it wrong is the most expensive modeling
mistake available, because every downstream metric inherits the error silently.

| Table | One row is | Rows per run | Natural key |
|---|---|---|---|
| `bronze.riot_league_entries` | one API response page | ~1 | `meta_source_file` |
| `bronze.riot_matches` | one match response | ~650 | `match_id` |
| `bronze.riot_match_timelines` | one timeline response | ~650 | `match_id` |
| `harmonized.matches` | one match | ~650 | `match_id` |
| `harmonized.match_participants` | one match × one player | ~6,500 | `match_id`, `participant_id` |
| `harmonized.match_teams` | one match × one team | ~1,300 | `match_id`, `team_id` |
| `harmonized.participant_frames` | one match × one player × one minute | ~195,000 | `match_id`, `participant_id`, `frame_minute` |
| `harmonized.timeline_events` | one filtered timeline event | ~300,000 | `match_id`, `event_index` |
| `harmonized.league_entries` | one player × one ladder snapshot | ~300 | `snapshot_date`, `player_sk` |

Volumes assume the scope in [ADR-0003](../adr/0003-data-source-scope-kr-challenger.md):
KR Challenger, ~300 players, 3 matches sampled per player, ~30% overlap after deduplication.

## Bronze

Bronze tables are structurally identical by design. They differ only in which endpoint they
came from.

```sql
CREATE TABLE mls.bronze.riot_matches (
  match_id               STRING   COMMENT 'Natural key extracted for idempotency only; no other field is parsed',
  payload                VARIANT  COMMENT 'Unmodified API response body',
  meta_source            STRING   COMMENT 'Always "riot"',
  meta_endpoint          STRING   COMMENT 'e.g. /lol/match/v5/matches/{matchId}',
  meta_platform_id       STRING   COMMENT 'Platform routing value, e.g. kr',
  meta_region            STRING   COMMENT 'Regional routing value, e.g. asia',
  meta_request_params    STRING   COMMENT 'JSON-encoded request parameters',
  meta_requested_at      TIMESTAMP COMMENT 'When the HTTP call was made',
  meta_source_file       STRING   COMMENT 'Landing-zone file this row came from',
  meta_ingested_at       TIMESTAMP COMMENT 'When the row was written to bronze',
  meta_pipeline_run_id   STRING
)
COMMENT 'Raw match-v5 responses, append-only. Never modified, never backfilled in place.'
```

Two deliberate choices:

**`match_id` is extracted, everything else is not.** Storing the natural key as a column is a
technical requirement for idempotent deduplication and for partition pruning. It is a copy,
not a transformation — the same value remains inside `payload`. Treating "as-is" as "not even
the key" would mean a full `VARIANT` scan for every merge.

**All metadata columns are prefixed `meta_`.** Anyone opening the table can see at a glance
which columns are the payload and which are the ingestion trail.

### Why `VARIANT` and not `STRING`

| | `STRING` | `VARIANT` |
|---|---|---|
| fidelity to the response | complete | complete |
| access | `get_json_object(payload, '$.info.gameVersion')` | `payload:info.gameVersion::string` |
| read cost | decompresses and scans the whole document | shredded per field; reads only the fields referenced |
| original types | lost — everything returns text | preserved (number, boolean, null) |
| schema drift | indifferent, but `from_json` requires a declared schema downstream | no schema is ever declared |
| maturity | universal | newer; `16 MB` limit per value |

`match-v5` payloads are deeply nested, contain several hundred optional fields, and Riot adds
fields between patches without notice. That is precisely the case `VARIANT` exists for.

Risk accepted and tracked: timeline payloads are 2–5 MB against a 16 MB per-value ceiling.
See [ADR-0004](../adr/0004-raw-payload-as-variant.md) and the
[validation plan](../operations/validation-plan.md).

## Harmonized

### `harmonized.matches`

| Column | Type | Notes |
|---|---|---|
| `match_id` | STRING | |
| `platform_id` | STRING | `kr` |
| `region` | STRING | `asia` |
| `game_version` | STRING | full Riot version string |
| `patch` | STRING | derived: first two components of `game_version`, e.g. `15.19` |
| `queue_id` | INT | 420 = Ranked Solo/Duo |
| `game_mode` | STRING | |
| `game_type` | STRING | |
| `map_id` | INT | |
| `game_started_at` | TIMESTAMP | |
| `game_date` | DATE | derived, used for partitioning and freshness |
| `game_duration_seconds` | INT | |
| `ended_in_early_surrender` | BOOLEAN | from the participant payload |
| `is_remake` | BOOLEAN | derived: `game_duration_seconds < 300 OR ended_in_early_surrender` |
| `winning_team_id` | INT | |
| `meta_*` | | audit columns |

`patch` is derived here rather than in a view because the derivation is mechanical and
stable. `is_remake` is derived here, but **not filtered** here — see the consumption layer.

### `harmonized.match_participants`

The primary fact. One row per player per match.

| Column | Type | Notes |
|---|---|---|
| `match_id`, `participant_id` | STRING, INT | key |
| `player_sk` | STRING | `HMAC-SHA256(puuid, salt)` — never the raw `puuid` |
| `champion_id`, `champion_name` | INT, STRING | |
| `champion_level` | INT | |
| `team_id` | INT | 100 / 200 |
| `team_position` | STRING | `TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM`, `UTILITY` |
| `individual_position`, `lane`, `role` | STRING | Riot's other position fields, kept for comparison |
| `kills`, `deaths`, `assists` | INT | |
| `kda` | DOUBLE | derived: `(kills + assists) / GREATEST(deaths, 1)` |
| `gold_earned` | INT | |
| `total_damage_dealt_to_champions` | INT | |
| `total_minions_killed`, `neutral_minions_killed` | INT | |
| `champ_experience` | INT | |
| `vision_score`, `wards_placed`, `wards_killed` | INT | |
| `summoner_spell_1_id`, `summoner_spell_2_id` | INT | |
| `item_0` … `item_6` | INT | final inventory |
| `primary_rune_style`, `sub_rune_style` | INT | |
| `is_win` | BOOLEAN | |
| `is_first_blood_kill` | BOOLEAN | |
| `time_played_seconds` | INT | |
| `meta_*` | | audit columns |

Expectations applied here: `champion_name IS NOT NULL`, `kills >= 0`, `deaths >= 0`,
`assists >= 0`, `gold_earned >= 0`, `team_id IN (100, 200)`. Violations are dropped and
counted.

### `harmonized.match_teams`

| Column | Type | Notes |
|---|---|---|
| `match_id`, `team_id` | STRING, INT | key |
| `is_win` | BOOLEAN | |
| `bans` | ARRAY&lt;STRUCT&lt;champion_id INT, pick_turn INT&gt;&gt; | kept nested; ban rate is computed in a view |
| `champion_kills`, `tower_kills`, `inhibitor_kills` | INT | |
| `baron_kills`, `dragon_kills`, `rift_herald_kills`, `horde_kills` | INT | |
| `has_first_blood`, `has_first_tower`, `has_first_dragon`, `has_first_baron`, `has_first_inhibitor`, `has_first_rift_herald` | BOOLEAN | |
| `meta_*` | | |

### `harmonized.participant_frames`

Minute-by-minute economy. This is what makes "gold difference at minute 15" possible.

| Column | Type | Notes |
|---|---|---|
| `match_id`, `participant_id`, `frame_minute` | STRING, INT, INT | key |
| `timestamp_ms` | BIGINT | |
| `total_gold`, `current_gold` | INT | |
| `xp`, `level` | INT | |
| `minions_killed`, `jungle_minions_killed` | INT | |
| `damage_done_to_champions` | INT | cumulative, from `damageStats` |
| `position_x`, `position_y` | INT | |
| `time_enemy_spent_controlled` | INT | |
| `meta_*` | | |

### `harmonized.timeline_events`

Filtered to four event types; see [ADR-0015](../adr/0015-timeline-event-type-filtering.md).

| Column | Type | Notes |
|---|---|---|
| `match_id`, `event_index` | STRING, INT | key |
| `timestamp_ms`, `frame_minute` | BIGINT, INT | |
| `event_type` | STRING | `CHAMPION_KILL`, `ELITE_MONSTER_KILL`, `BUILDING_KILL`, `ITEM_PURCHASED` |
| `killer_participant_id`, `victim_participant_id` | INT | nullable |
| `assisting_participant_ids` | ARRAY&lt;INT&gt; | nullable |
| `monster_type`, `monster_sub_type` | STRING | nullable |
| `building_type`, `tower_type`, `lane_type` | STRING | nullable |
| `item_id` | INT | nullable |
| `team_id` | INT | nullable |
| `position_x`, `position_y` | INT | nullable |
| `bounty` | INT | nullable |
| `meta_*` | | |

The table is intentionally sparse: one wide table with nullable columns per event family,
rather than four narrow tables. The reason is that almost every analysis crosses event types
on a shared time axis, and a single table avoids four-way unions in every query. The cost is
nullability that the consumer must understand, which is what the column comments are for.

### `harmonized.league_entries`

| Column | Type | Notes |
|---|---|---|
| `snapshot_date` | DATE | key |
| `player_sk` | STRING | key — pseudonymized |
| `platform_id`, `queue` | STRING | |
| `tier`, `division` | STRING | `CHALLENGER`, `I` |
| `league_points` | INT | |
| `wins`, `losses` | INT | |
| `win_rate_pct` | DOUBLE | derived |
| `is_veteran`, `is_inactive`, `is_fresh_blood`, `is_hot_streak` | BOOLEAN | |
| `meta_*` | | |

A snapshot table, not an SCD: each run appends a dated picture of the ladder. Ladder movement
is derived by comparing snapshots in a view.

## Consumption

Everything here is a **view**. Nothing is materialized.

### Dimensions

| View | Grain | Source |
|---|---|---|
| `dim_champion` | one champion | `DISTINCT champion_id, champion_name` from `match_participants` |
| `dim_patch` | one patch | `DISTINCT patch` from `matches`, with first/last seen dates |
| `dim_queue` | one queue id | static mapping, maintained as a small seed in the repo |
| `dim_team_position` | one position | static mapping with display ordering |

`dim_champion` is derived from observed data rather than enriched from Data Dragon. That is a
limitation: champion class, release date and icon are not available. Data Dragon enrichment
is on the roadmap, not in scope.

### Facts

| View | Grain | Business filter applied |
|---|---|---|
| `fct_match_participant` | match × player | `NOT is_remake AND queue_id = 420` |
| `fct_match_team` | match × team | same |
| `fct_participant_frame` | match × player × minute | same |
| `fct_timeline_event` | event | same |

The business filter is stated once, in the fact views, and inherited by everything above
them. Changing the analytical scope — including ARAM, including remakes — is an edit to these
four view definitions.

### Aggregates

| View | Grain | Key measures |
|---|---|---|
| `agg_champion_by_patch` | champion × patch | `matches_played`, `pick_rate_pct`, `ban_rate_pct`, `win_rate_pct`, `avg_kda` |
| `agg_champion_by_patch_lane` | champion × patch × team_position | same, split by lane |
| `agg_champion_gold_curve` | champion × patch × minute | `avg_total_gold`, `avg_xp`, `avg_cs` |
| `agg_objective_impact` | patch × objective | win rate when the team takes the objective first |
| `agg_ladder_movement` | snapshot_date | challenger population, LP distribution, churn vs previous snapshot |

Rate measures are expressed against an explicit denominator in the view definition — pick
rate over matches in the patch, ban rate over team-ban slots in the patch. Rates without a
stated denominator are the most common silent error in game analytics.

## Ops

```sql
CREATE TABLE mls.ops.dq_metrics (
  measured_at          TIMESTAMP,
  pipeline_run_id      STRING,
  layer                STRING   COMMENT 'bronze | harmonized | consumption',
  table_name           STRING,
  metric_name          STRING   COMMENT 'row_count | freshness_hours | null_rate | drop_rate | distinct_ratio',
  metric_column        STRING   COMMENT 'nullable; set for column-scoped metrics',
  metric_value         DOUBLE,
  threshold            DOUBLE   COMMENT 'nullable',
  status               STRING   COMMENT 'PASS | WARN | FAIL'
)
COMMENT 'Long-format data quality measurements, one row per metric per run.'
```

Long format rather than one column per metric: adding a new check is an insert, not a schema
migration, and the dashboard pivots at query time.

Metric families: **volumetry** (row counts and run-over-run variation), **freshness** (hours
since the newest `game_date`), **fullness** (null rate on required columns), **validity**
(drop rate from expectations), **uniqueness** (distinct natural keys over row count).
