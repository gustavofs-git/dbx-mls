# Architecture Patterns: Silver and Gold Layers

**Domain:** Medallion Architecture — Riot Games Match-V5 JSON unnesting
**Researched:** 2026-04-07
**Scope:** Silver transformation patterns, Delta Lake table design, Unity Catalog governance, Gold aggregation candidates

---

## Recommended Architecture Overview

```
bronze.match_raw          (raw JSON string column + ingestion metadata)
    |
    | [Silver Job: match_transformer.py]
    v
silver.match              (flat info-level fields, 1 row per match)
silver.match_participants (147 flat columns, 1 row per participant per match)
silver.match_teams        (team-level, 1 row per team per match)
silver.match_teams_bans   (1 row per ban per team per match — exploded from bans[])
silver.match_teams_objectives (1 row per objective per team — pivoted from objectives map)

bronze.match_timeline_raw (raw JSON string column + ingestion metadata)
    |
    | [Silver Job: timeline_transformer.py]
    v
silver.match_timeline_frames           (1 row per frame)
silver.match_timeline_participant_frames (1 row per participant per frame — map exploded)
silver.match_timeline_events           (1 row per event per frame — events[] exploded)
```

**Design principle:** Bronze is append-only raw storage. Silver is the first time JSON is parsed
and typed. All structural work — explode, flatten, cast — happens at the Silver boundary.
Gold reads only from Silver and never touches Bronze.

---

## 1. JSON Parsing: Bronze vs Silver Boundary

**Decision: Keep raw JSON as STRING in Bronze; parse at Silver.**

Bronze tables store the API response verbatim in a column named `raw_json STRING`.
No `from_json` or `schema_of_json` is called during ingestion. Ingestion metadata
(`_ingested_at`, `_source`, `_region`, `_tier`, `_batch_id`) are the only typed columns.

```
bronze.match_raw
  match_id        STRING   -- extracted from URL/path, NOT from JSON body
  raw_json        STRING   -- verbatim Riot API response, no modification
  _ingested_at    TIMESTAMP
  _source         STRING   -- "riot_match_v5"
  _region         STRING   -- runtime param: "KR"
  _tier           STRING   -- runtime param: "CHALLENGER"
  _batch_id       STRING   -- UUID per ingestion run, enables replay
```

**Why this matters:**
- Bronze is replayable. If Riot adds a field, you do not need to re-call the API.
  Re-run only the Silver job with the updated schema.
- `schema_of_json` infers from a single sample and is unreliable for production.
  The Silver job owns an explicit, version-controlled `StructType` definition.
- Storing parsed structs in Bronze locks you into a schema at ingest time,
  defeating the purpose of the raw layer.

**Confidence: HIGH** (official Databricks Medallion pattern; community consensus)

---

## 2. Silver Spark Functions: Unnesting the Match-V5 Participant Object

### 2.1 Bronze → silver.match + silver.match_participants

The root transformation reads `raw_json`, applies `from_json` with a pre-defined
`StructType`, then uses `explode` on the `participants` array.

```python
from pyspark.sql import functions as F
from pyspark.sql.types import StructType  # schema defined in schemas/match_schema.py

def transform_match(bronze_df, match_schema: StructType):
    # Step 1: Parse the raw JSON string into a struct
    parsed = bronze_df.withColumn(
        "data",
        F.from_json(F.col("raw_json"), match_schema)
    )

    # Step 2: Extract flat match-level fields from info
    match_df = parsed.select(
        F.col("data.metadata.matchId").alias("match_id"),
        F.col("data.info.gameId").alias("game_id"),
        F.col("data.info.gameMode").alias("game_mode"),
        F.col("data.info.gameType").alias("game_type"),
        F.col("data.info.gameDuration").alias("game_duration_s"),
        F.col("data.info.gameVersion").alias("game_version"),
        F.col("data.info.gameCreation").alias("game_creation_ms"),
        F.col("data.info.gameStartTimestamp").alias("game_start_ts_ms"),
        F.col("data.info.gameEndTimestamp").alias("game_end_ts_ms"),
        F.col("data.info.queueId").alias("queue_id"),
        F.col("data.info.platformId").alias("platform_id"),
        F.col("data.info.mapId").alias("map_id"),
        F.col("data.info.endOfGameResult").alias("end_of_game_result"),
        # Lineage columns
        F.col("_ingested_at"),
        F.col("_region"),
        F.col("_tier"),
        F.col("_batch_id"),
        F.current_timestamp().alias("_transformed_at"),
    )

    # Step 3: Explode participants array — produces 10 rows per match
    participants_exploded = parsed.select(
        F.col("data.metadata.matchId").alias("match_id"),
        F.col("_ingested_at"),
        F.col("_region"),
        F.col("_tier"),
        F.col("_batch_id"),
        F.explode(F.col("data.info.participants")).alias("p"),
    )

    # Step 4: Flatten all 147 participant fields
    # challenges (125 fields) and perks are handled separately — see Section 4
    participant_df = participants_exploded.select(
        "match_id", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("p.participantId").alias("participant_id"),
        F.col("p.puuid").alias("puuid"),
        F.col("p.riotIdGameName").alias("riot_id_game_name"),
        F.col("p.riotIdTagline").alias("riot_id_tagline"),
        F.col("p.teamId").alias("team_id"),
        F.col("p.championId").alias("champion_id"),
        F.col("p.championName").alias("champion_name"),
        F.col("p.individualPosition").alias("individual_position"),
        F.col("p.teamPosition").alias("team_position"),
        F.col("p.lane").alias("lane"),
        F.col("p.role").alias("role"),
        F.col("p.kills").alias("kills"),
        F.col("p.deaths").alias("deaths"),
        F.col("p.assists").alias("assists"),
        F.col("p.win").alias("win"),
        F.col("p.champLevel").alias("champ_level"),
        F.col("p.champExperience").alias("champ_experience"),
        F.col("p.goldEarned").alias("gold_earned"),
        F.col("p.goldSpent").alias("gold_spent"),
        F.col("p.totalMinionsKilled").alias("total_minions_killed"),
        F.col("p.neutralMinionsKilled").alias("neutral_minions_killed"),
        F.col("p.totalAllyJungleMinionsKilled").alias("total_ally_jungle_minions_killed"),
        F.col("p.totalEnemyJungleMinionsKilled").alias("total_enemy_jungle_minions_killed"),
        F.col("p.totalDamageDealtToChampions").alias("total_damage_dealt_to_champions"),
        F.col("p.physicalDamageDealtToChampions").alias("physical_damage_dealt_to_champions"),
        F.col("p.magicDamageDealtToChampions").alias("magic_damage_dealt_to_champions"),
        F.col("p.trueDamageDealtToChampions").alias("true_damage_dealt_to_champions"),
        F.col("p.totalDamageDealt").alias("total_damage_dealt"),
        F.col("p.totalDamageTaken").alias("total_damage_taken"),
        F.col("p.damageSelfMitigated").alias("damage_self_mitigated"),
        F.col("p.damageDealtToObjectives").alias("damage_dealt_to_objectives"),
        F.col("p.damageDealtToTurrets").alias("damage_dealt_to_turrets"),
        F.col("p.damageDealtToBuildings").alias("damage_dealt_to_buildings"),
        F.col("p.damageDealtToEpicMonsters").alias("damage_dealt_to_epic_monsters"),
        F.col("p.totalHeal").alias("total_heal"),
        F.col("p.totalHealsOnTeammates").alias("total_heals_on_teammates"),
        F.col("p.totalDamageShieldedOnTeammates").alias("total_damage_shielded_on_teammates"),
        F.col("p.visionScore").alias("vision_score"),
        F.col("p.wardsPlaced").alias("wards_placed"),
        F.col("p.wardsKilled").alias("wards_killed"),
        F.col("p.visionWardsBoughtInGame").alias("vision_wards_bought_in_game"),
        F.col("p.sightWardsBoughtInGame").alias("sight_wards_bought_in_game"),
        F.col("p.detectorWardsPlaced").alias("detector_wards_placed"),
        F.col("p.firstBloodKill").alias("first_blood_kill"),
        F.col("p.firstBloodAssist").alias("first_blood_assist"),
        F.col("p.firstTowerKill").alias("first_tower_kill"),
        F.col("p.firstTowerAssist").alias("first_tower_assist"),
        F.col("p.turretKills").alias("turret_kills"),
        F.col("p.turretTakedowns").alias("turret_takedowns"),
        F.col("p.turretsLost").alias("turrets_lost"),
        F.col("p.inhibitorKills").alias("inhibitor_kills"),
        F.col("p.inhibitorTakedowns").alias("inhibitor_takedowns"),
        F.col("p.inhibitorsLost").alias("inhibitors_lost"),
        F.col("p.nexusKills").alias("nexus_kills"),
        F.col("p.nexusTakedowns").alias("nexus_takedowns"),
        F.col("p.nexusLost").alias("nexus_lost"),
        F.col("p.baronKills").alias("baron_kills"),
        F.col("p.dragonKills").alias("dragon_kills"),
        F.col("p.objectivesStolen").alias("objectives_stolen"),
        F.col("p.objectivesStolenAssists").alias("objectives_stolen_assists"),
        F.col("p.killingSprees").alias("killing_sprees"),
        F.col("p.largestKillingSpree").alias("largest_killing_spree"),
        F.col("p.largestMultiKill").alias("largest_multi_kill"),
        F.col("p.doubleKills").alias("double_kills"),
        F.col("p.tripleKills").alias("triple_kills"),
        F.col("p.quadraKills").alias("quadra_kills"),
        F.col("p.pentaKills").alias("penta_kills"),
        F.col("p.unrealKills").alias("unreal_kills"),
        F.col("p.longestTimeSpentLiving").alias("longest_time_spent_living"),
        F.col("p.totalTimeSpentDead").alias("total_time_spent_dead"),
        F.col("p.timeCCingOthers").alias("time_ccing_others"),
        F.col("p.totalTimeCCDealt").alias("total_time_cc_dealt"),
        F.col("p.timePlayed").alias("time_played"),
        F.col("p.spell1Casts").alias("spell1_casts"),
        F.col("p.spell2Casts").alias("spell2_casts"),
        F.col("p.spell3Casts").alias("spell3_casts"),
        F.col("p.spell4Casts").alias("spell4_casts"),
        F.col("p.summoner1Id").alias("summoner1_id"),
        F.col("p.summoner2Id").alias("summoner2_id"),
        F.col("p.summoner1Casts").alias("summoner1_casts"),
        F.col("p.summoner2Casts").alias("summoner2_casts"),
        F.col("p.item0").alias("item0"),
        F.col("p.item1").alias("item1"),
        F.col("p.item2").alias("item2"),
        F.col("p.item3").alias("item3"),
        F.col("p.item4").alias("item4"),
        F.col("p.item5").alias("item5"),
        F.col("p.item6").alias("item6"),  # trinket
        F.col("p.itemsPurchased").alias("items_purchased"),
        F.col("p.consumablesPurchased").alias("consumables_purchased"),
        F.col("p.allInPings").alias("all_in_pings"),
        F.col("p.assistMePings").alias("assist_me_pings"),
        F.col("p.basicPings").alias("basic_pings"),
        F.col("p.commandPings").alias("command_pings"),
        F.col("p.dangerPings").alias("danger_pings"),
        F.col("p.enemyMissingPings").alias("enemy_missing_pings"),
        F.col("p.enemyVisionPings").alias("enemy_vision_pings"),
        F.col("p.getBackPings").alias("get_back_pings"),
        F.col("p.holdPings").alias("hold_pings"),
        F.col("p.needVisionPings").alias("need_vision_pings"),
        F.col("p.onMyWayPings").alias("on_my_way_pings"),
        F.col("p.pushPings").alias("push_pings"),
        F.col("p.retreatPings").alias("retreat_pings"),
        F.col("p.visionClearedPings").alias("vision_cleared_pings"),
        F.col("p.gameEndedInEarlySurrender").alias("game_ended_in_early_surrender"),
        F.col("p.gameEndedInSurrender").alias("game_ended_in_surrender"),
        F.col("p.teamEarlySurrendered").alias("team_early_surrendered"),
        F.col("p.eligibleForProgression").alias("eligible_for_progression"),
        F.col("p.summonerId").alias("summoner_id"),
        F.col("p.summonerLevel").alias("summoner_level"),
        F.col("p.profileIcon").alias("profile_icon"),
        F.col("p.championTransform").alias("champion_transform"),
        F.col("p.placement").alias("placement"),
        F.col("p.subteamPlacement").alias("subteam_placement"),
        F.col("p.playerSubteamId").alias("player_subteam_id"),
        F.col("p.roleBoundItem").alias("role_bound_item"),
        F.col("p.PlayerScore0").alias("player_score_0"),
        F.col("p.PlayerScore1").alias("player_score_1"),
        F.col("p.PlayerScore2").alias("player_score_2"),
        F.col("p.PlayerScore3").alias("player_score_3"),
        F.col("p.PlayerScore4").alias("player_score_4"),
        F.col("p.PlayerScore5").alias("player_score_5"),
        F.col("p.PlayerScore6").alias("player_score_6"),
        F.col("p.PlayerScore7").alias("player_score_7"),
        F.col("p.PlayerScore8").alias("player_score_8"),
        F.col("p.PlayerScore9").alias("player_score_9"),
        F.col("p.PlayerScore10").alias("player_score_10"),
        F.col("p.PlayerScore11").alias("player_score_11"),
        # challenges and perks handled via separate flatten helper
        F.col("p.challenges").alias("challenges"),  # STRUCT for now; see Section 4
        F.col("p.perks").alias("perks"),             # STRUCT for now; see Section 4
        F.col("p.missions").alias("missions"),       # STRUCT for now; see Section 4
        F.col("p.PlayerBehavior").alias("player_behavior"),  # STRUCT
        F.current_timestamp().alias("_transformed_at"),
    )

    return match_df, participant_df
```

### 2.2 Teams: explode + pivot the objectives map

The `objectives` field is a **map of structs** (8 named keys: atakhan, baron, champion,
dragon, horde, inhibitor, riftHerald, tower). The canonical approach is to flatten each
key to its own column pair (`{name}_first`, `{name}_kills`) rather than using `explode`
on a map, because the key set is known and bounded.

```python
def transform_teams(parsed_df):
    # Step 1: explode the teams array — 2 rows per match
    teams_exploded = parsed_df.select(
        F.col("data.metadata.matchId").alias("match_id"),
        F.col("_ingested_at"), F.col("_region"), F.col("_tier"), F.col("_batch_id"),
        F.explode(F.col("data.info.teams")).alias("t"),
    )

    # Step 2: flat teams table
    teams_df = teams_exploded.select(
        "match_id", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("t.teamId").alias("team_id"),
        F.col("t.win").alias("win"),
        # objectives — flatten known keys
        F.col("t.objectives.atakhan.first").alias("atakhan_first"),
        F.col("t.objectives.atakhan.kills").alias("atakhan_kills"),
        F.col("t.objectives.baron.first").alias("baron_first"),
        F.col("t.objectives.baron.kills").alias("baron_kills"),
        F.col("t.objectives.champion.first").alias("champion_first"),
        F.col("t.objectives.champion.kills").alias("champion_kills"),
        F.col("t.objectives.dragon.first").alias("dragon_first"),
        F.col("t.objectives.dragon.kills").alias("dragon_kills"),
        F.col("t.objectives.horde.first").alias("horde_first"),
        F.col("t.objectives.horde.kills").alias("horde_kills"),
        F.col("t.objectives.inhibitor.first").alias("inhibitor_first"),
        F.col("t.objectives.inhibitor.kills").alias("inhibitor_kills"),
        F.col("t.objectives.riftHerald.first").alias("rift_herald_first"),
        F.col("t.objectives.riftHerald.kills").alias("rift_herald_kills"),
        F.col("t.objectives.tower.first").alias("tower_first"),
        F.col("t.objectives.tower.kills").alias("tower_kills"),
        # feats
        F.col("t.feats.EPIC_MONSTER_KILL.featState").alias("feat_epic_monster_kill"),
        F.col("t.feats.FIRST_BLOOD.featState").alias("feat_first_blood"),
        F.col("t.feats.FIRST_TURRET.featState").alias("feat_first_turret"),
        F.current_timestamp().alias("_transformed_at"),
    )

    # Step 3: bans sub-table — use inline() on array of structs
    # inline() is preferred over explode() for array-of-struct because it
    # automatically promotes each struct field to a top-level column
    bans_df = teams_exploded.select(
        "match_id", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("t.teamId").alias("team_id"),
        F.inline(F.col("t.bans")),   # produces champion_id, pick_turn columns
    ).withColumn("_transformed_at", F.current_timestamp())

    return teams_df, bans_df
```

**Why `inline()` over `explode()` for bans:** `explode()` on an array-of-struct
produces a single struct column that must be selected again. `inline()` directly
projects all struct fields as individual columns in one step, reducing code and
one Spark stage. Use `inline_outer()` if any `bans` array could be null or empty
(guaranteed not for Match-V5 since every draft has 5 bans per team, but defensive
coding is good practice).

**Confidence: HIGH** (PySpark official docs confirm inline semantics)

### 2.3 Timeline: participantFrames map explosion

`participantFrames` is a **map** keyed by participant ID string (not an array).
Maps are exploded with `explode` which yields `key` and `value` columns.

```python
def transform_timeline(bronze_timeline_df, timeline_schema: StructType):
    parsed = bronze_timeline_df.withColumn(
        "tl",
        F.from_json(F.col("raw_json"), timeline_schema)
    )

    # Level 1: explode frames array
    frames_exploded = parsed.select(
        F.col("tl.metadata.matchId").alias("match_id"),
        F.col("_ingested_at"), F.col("_region"), F.col("_tier"), F.col("_batch_id"),
        F.explode(F.col("tl.info.frames")).alias("frame"),
    )

    # Level 2: flat frames table
    frames_df = frames_exploded.select(
        "match_id", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("frame.timestamp").alias("frame_timestamp_ms"),
        F.size(F.map_values(F.col("frame.participantFrames"))).alias("participant_frame_count"),
        F.size(F.col("frame.events")).alias("event_count"),
        F.current_timestamp().alias("_transformed_at"),
    )

    # Level 3: explode participantFrames MAP — key = participant_id string
    pf_exploded = frames_exploded.select(
        "match_id", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("frame.timestamp").alias("frame_timestamp_ms"),
        F.explode(F.col("frame.participantFrames")).alias("participant_id_str", "pf"),
    )

    # Level 4: flatten nested structs inside participant frame
    pf_df = pf_exploded.select(
        "match_id", "frame_timestamp_ms", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("participant_id_str").cast("integer").alias("participant_id"),
        F.col("pf.currentGold").alias("current_gold"),
        F.col("pf.goldPerSecond").alias("gold_per_second"),
        F.col("pf.totalGold").alias("total_gold"),
        F.col("pf.level").alias("level"),
        F.col("pf.xp").alias("xp"),
        F.col("pf.minionsKilled").alias("minions_killed"),
        F.col("pf.jungleMinionsKilled").alias("jungle_minions_killed"),
        F.col("pf.timeEnemySpentControlled").alias("time_enemy_spent_controlled"),
        F.col("pf.position.x").alias("pos_x"),
        F.col("pf.position.y").alias("pos_y"),
        # championStats — 25 fields, flatten all
        F.col("pf.championStats.abilityHaste").alias("stat_ability_haste"),
        F.col("pf.championStats.abilityPower").alias("stat_ability_power"),
        F.col("pf.championStats.armor").alias("stat_armor"),
        F.col("pf.championStats.armorPen").alias("stat_armor_pen"),
        F.col("pf.championStats.armorPenPercent").alias("stat_armor_pen_percent"),
        F.col("pf.championStats.attackDamage").alias("stat_attack_damage"),
        F.col("pf.championStats.attackSpeed").alias("stat_attack_speed"),
        F.col("pf.championStats.bonusArmorPenPercent").alias("stat_bonus_armor_pen_percent"),
        F.col("pf.championStats.bonusMagicPenPercent").alias("stat_bonus_magic_pen_percent"),
        F.col("pf.championStats.ccReduction").alias("stat_cc_reduction"),
        F.col("pf.championStats.cooldownReduction").alias("stat_cooldown_reduction"),
        F.col("pf.championStats.health").alias("stat_health"),
        F.col("pf.championStats.healthMax").alias("stat_health_max"),
        F.col("pf.championStats.healthRegen").alias("stat_health_regen"),
        F.col("pf.championStats.lifesteal").alias("stat_lifesteal"),
        F.col("pf.championStats.magicPen").alias("stat_magic_pen"),
        F.col("pf.championStats.magicPenPercent").alias("stat_magic_pen_percent"),
        F.col("pf.championStats.magicResist").alias("stat_magic_resist"),
        F.col("pf.championStats.movementSpeed").alias("stat_movement_speed"),
        F.col("pf.championStats.omnivamp").alias("stat_omnivamp"),
        F.col("pf.championStats.physicalVamp").alias("stat_physical_vamp"),
        F.col("pf.championStats.power").alias("stat_power"),
        F.col("pf.championStats.powerMax").alias("stat_power_max"),
        F.col("pf.championStats.powerRegen").alias("stat_power_regen"),
        F.col("pf.championStats.spellVamp").alias("stat_spell_vamp"),
        # damageStats — 12 fields
        F.col("pf.damageStats.magicDamageDone").alias("dmg_magic_done"),
        F.col("pf.damageStats.magicDamageDoneToChampions").alias("dmg_magic_done_to_champions"),
        F.col("pf.damageStats.magicDamageTaken").alias("dmg_magic_taken"),
        F.col("pf.damageStats.physicalDamageDone").alias("dmg_physical_done"),
        F.col("pf.damageStats.physicalDamageDoneToChampions").alias("dmg_physical_done_to_champions"),
        F.col("pf.damageStats.physicalDamageTaken").alias("dmg_physical_taken"),
        F.col("pf.damageStats.totalDamageDone").alias("dmg_total_done"),
        F.col("pf.damageStats.totalDamageDoneToChampions").alias("dmg_total_done_to_champions"),
        F.col("pf.damageStats.totalDamageTaken").alias("dmg_total_taken"),
        F.col("pf.damageStats.trueDamageDone").alias("dmg_true_done"),
        F.col("pf.damageStats.trueDamageDoneToChampions").alias("dmg_true_done_to_champions"),
        F.col("pf.damageStats.trueDamageTaken").alias("dmg_true_taken"),
        F.current_timestamp().alias("_transformed_at"),
    )

    # Level 3b: explode events array — use explode (not inline) because events
    # are polymorphic objects with different fields per event type
    events_df = frames_exploded.select(
        "match_id", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("frame.timestamp").alias("frame_timestamp_ms"),
        F.explode(F.col("frame.events")).alias("event"),
    ).select(
        "match_id", "frame_timestamp_ms", "_ingested_at", "_region", "_tier", "_batch_id",
        F.col("event.type").alias("event_type"),
        F.col("event.timestamp").alias("event_timestamp_ms"),
        F.col("event.realTimestamp").alias("event_real_timestamp_ms"),
        # common optional fields — null for events that don't have them
        F.col("event.participantId").alias("participant_id"),
        F.col("event.killerId").alias("killer_id"),
        F.col("event.victimId").alias("victim_id"),
        F.col("event.assistingParticipantIds").alias("assisting_participant_ids"),
        F.col("event.itemId").alias("item_id"),
        F.col("event.skillSlot").alias("skill_slot"),
        F.col("event.buildingType").alias("building_type"),
        F.col("event.towerType").alias("tower_type"),
        F.col("event.monsterType").alias("monster_type"),
        F.col("event.monsterSubType").alias("monster_sub_type"),
        F.col("event.wardType").alias("ward_type"),
        F.col("event.position.x").alias("pos_x"),
        F.col("event.position.y").alias("pos_y"),
        F.current_timestamp().alias("_transformed_at"),
    )

    return frames_df, pf_df, events_df
```

---

## 3. The `challenges` Object: Flatten vs Keep as Struct

**Decision: Flatten all 125 fields in `silver.match_participants`. Do NOT keep as STRUCT.**

**Rationale:**

1. SQL analysts cannot query `challenges.kda` without knowing the STRUCT syntax.
   Flat columns are universally accessible to BI tools, SQL notebooks, and Gold jobs.

2. The 125 challenges fields are individually meaningful for analytics
   (e.g., `kda`, `visionScoreAdvantageLaneOpponent`, `soloKills`,
   `teamDamagePercentage`). Gold aggregations will GROUP BY champion and
   average individual challenge metrics. That requires flat columns.

3. A 272-column table (147 original + 125 challenges + lineage) is wide but
   valid for Delta Lake. Databricks supports column statistics for the first
   32 columns by default; additional columns are accessible without stats.
   The performance impact is negligible on reads filtered by `match_id`
   or `champion_id`.

4. `perks` (2 sub-objects: `statPerks`, `selections` array) and `missions`
   (12 fields) should also be flattened. `perks.statPerks` has 3 integer
   fields. `perks.selections` is a small array of rune selections — use
   `inline()` to expand it or flatten indices as `perk_sel_0_*` columns.

**Implementation note for challenges:** Use a helper function that iterates
through a known list of challenge field names and calls `.withColumn` or
builds the select list programmatically to avoid a 125-line select statement:

```python
CHALLENGE_FIELDS = [
    "12AssistStreakCount", "HealFromMapSources", "InfernalScalePickup",
    "SWARM_DefeatAatrox", "SWARM_DefeatBriar", "SWARM_DefeatMiniBosses",
    "SWARM_EvolveWeapon", "SWARM_Have3Passives", "SWARM_KillEnemy",
    "SWARM_ReachLevel50", "SWARM_Survive15Min", "SWARM_WinWith5EvolvedWeapons",
    "abilityUses", "aceAfter15Minutes", "alliedJungleMonsterKills",
    "baronBuffGoldAdvantageOverThreshold", "blastConeOppositeOpponentCount",
    "bountyGold", "buffsStolen", "completeSupportQuestInTime",
    "controlWardsPlaced", "damagePerMinute", "damageTakenOnTeamPercentage",
    "dancedWithRiftHerald", "deathsByEnemyChamps", "dodgeSkillShotsSmallWindow",
    "doubleAces", "dragonTakedowns", "earliestBaron", "earliestDragonTakedown",
    "earliestElderDragon", "earlyLaningPhaseGoldExpAdvantage",
    "effectiveHealAndShielding", "elderDragonKillsWithOpposingSoul",
    "elderDragonMultikills", "enemyChampionImmobilizations", "enemyJungleMonsterKills",
    "epicMonsterKillsNearEnemyJungler", "epicMonsterKillsWithin30SecondsOfSpawn",
    "epicMonsterSteals", "epicMonsterStolenWithoutSmite",
    "firstTurretKilledTime", "flawlessAces", "fullTeamTakedown",
    "gameLength", "getTakedownsInAllLanesEarlyJungleAsLaner",
    "goldPerMinute", "hadAfkTeammate", "hadOpenNexus",
    "immobilizeAndKillWithAlly", "initialBuffCount", "initialCrabCount",
    "jungleCsBefore10Minutes", "junglerTakedownsNearDamagedEpicMonster",
    "kTurretsDestroyedBeforePlatesFall", "kda", "killAfterHiddenWithAlly",
    "killParticipation", "killedChampTookFullTeamDamageSurvived",
    "killingSprees", "killsNearEnemyTurret", "killsOnOtherLanesEarlyJungleAsLaner",
    "killsOnRecentlyHealedByAramPack", "killsUnderOwnTurret",
    "killsWithLastSpellCast", "landSkillShotsEarlyGame",
    "laneMinionsFirst10Minutes", "laningPhaseGoldExpAdvantage",
    "legendaryCount", "legendaryItemUsed", "lostAnInhibitor",
    "maxCsAdvantageOnLaneOpponent", "maxKillDeficit",
    "maxLevelLeadLaneOpponent", "mejaisFullStackInTime",
    "moreEnemyJungleThanOpponent", "multiKillOneSpell",
    "multikills", "multikillsAfterAggressiveFlash",
    "multiTurretRiftHeraldCount", "mythicItemUsed",
    "outerTurretExecutesBefore10Minutes", "outnumbered",
    "perfectDragonSoulsTaken", "perfectGame",
    "pickKillWithAlly", "poroExplosions",
    "quickCleanse", "quickFirstTurret", "quickSoloKills",
    "riftHeraldTakedowns", "saveAllyFromDeath",
    "scuttleCrabKills", "shortestTimeToAceFromFirstTakedown",
    "skillshotsDodged", "skillshotsHit",
    "snowballsHit", "soloBaronKills", "soloKills",
    "soloTurretsLategame", "stealthWardsPlaced", "survivedSingleDigitHpCount",
    "survivedThreeImmobilizesInFight", "takedownOnFirstTurret",
    "takedowns", "takedownsAfterGainingLevelAdvantage",
    "takedownsBeforeJungleMinionSpawn", "takedownsFirstXMinutes",
    "takedownsInAlcove", "takedownsInEnemyFountain",
    "teamBaronKills", "teamDamagePercentage", "teamElderDragonKills",
    "teamRiftHeraldKills", "teleportTakedowns",
    "threeWardsOneSweeperCount", "tookLargeDamageSurvived",
    "turretPlatesTaken", "turretsTakenWithRiftHerald",
    "turretTakedowns", "twentyMinionsIn3SecondsCount",
    "twoWardsOneSweeperCount", "unseenRecalls",
    "visionScoreAdvantageLaneOpponent", "visionScorePerMinute",
    "wardTakedowns", "wardTakedownsBefore20M",
    "wardsGuarded",
]

def flatten_challenges(df, struct_col="p"):
    """Flatten the challenges struct into prefixed flat columns."""
    select_exprs = []
    for field in CHALLENGE_FIELDS:
        # Field names like "12AssistStreakCount" are valid Spark struct keys
        # Use backtick quoting for names starting with digits
        safe_alias = field.lower().replace(" ", "_")
        select_exprs.append(
            F.col(f"{struct_col}.challenges.`{field}`").alias(f"chal_{safe_alias}")
        )
    return select_exprs
```

**Confidence: MEDIUM** (schema_report shows 125 challenge fields — exact field names
need validation against a live KR Challenger match response)

---

## 4. Delta Lake Table Design

### 4.1 Partitioning Strategy: Do NOT partition Silver tables

Databricks official docs state tables under 1 TB should not be partitioned.
The Silver tables in this project will stay well under 1 TB for a KR Challenger
dataset (200 players × ~20 matches × 10 participants = ~40,000 participant rows
per daily batch).

**Use Liquid Clustering instead of partitioning.**

Databricks recommends liquid clustering for ALL new Delta tables as of 2025.
Liquid clustering provides data skipping without the over-partitioning risk,
can be redefined without rewriting data, and is compatible with Unity Catalog
managed tables.

```sql
-- silver.match_participants: cluster on champion_id + individual_position
-- Most analytical queries filter on champion or position
CREATE TABLE lol_analytics.silver.match_participants (
  match_id STRING,
  participant_id INT,
  champion_id INT,
  champion_name STRING,
  individual_position STRING,
  -- ... all other columns
  _ingested_at TIMESTAMP,
  _region STRING,
  _tier STRING,
  _batch_id STRING,
  _transformed_at TIMESTAMP
)
CLUSTER BY (champion_id, individual_position);

-- silver.match_timeline_participant_frames: cluster on match_id
-- Timeline queries almost always filter by a specific match
CREATE TABLE lol_analytics.silver.match_timeline_participant_frames (...)
CLUSTER BY (match_id);

-- silver.match: cluster on platform_id (region filtering is common)
CREATE TABLE lol_analytics.silver.match (...)
CLUSTER BY (platform_id);
```

**For Automatic Liquid Clustering (DBR 15.4+):**
```sql
ALTER TABLE lol_analytics.silver.match_participants CLUSTER BY AUTO;
```

Automatic clustering analyzes query history and selects optimal keys.
Enable this after accumulating a few weeks of query patterns.

**Confidence: HIGH** (official Databricks docs, March 2026 update)

### 4.2 OPTIMIZE and VACUUM Schedule

```python
# Run after each Silver job completes
spark.sql("OPTIMIZE lol_analytics.silver.match_participants")
spark.sql("OPTIMIZE lol_analytics.silver.match_timeline_participant_frames")

# Run weekly (retain 7 days of history for time-travel)
spark.sql("VACUUM lol_analytics.silver.match_participants RETAIN 168 HOURS")
```

If Predictive Optimization is enabled in the Unity Catalog workspace, manual
OPTIMIZE jobs are unnecessary — disable the scheduled jobs to avoid double work.

---

## 5. Schema Evolution Strategy

**The core problem:** Riot Games adds new champion stats, ping types, or challenge
fields in patches without versioning the API. Bronze already handles this safely
(raw STRING column never breaks). The Silver schema evolution strategy covers
the transformation layer.

### 5.1 Explicit StructType Definitions in Version Control

Define the Bronze parsing schema as a Python `StructType` in `schemas/match_schema.py`.
This file is version controlled and is the single source of truth.

```
src/
  schemas/
    match_schema.py        # StructType for match_raw parsing
    timeline_schema.py     # StructType for match_timeline_raw parsing
```

**Never use `schema_of_json` or `inferSchema` in production Silver jobs.**
`schema_of_json` samples a single row and can miss nullable fields or
produce incorrect types. Use the explicit schema.

### 5.2 Handling New Fields from Riot API

When Riot adds a new field (e.g., a new challenge metric):

1. **Nothing breaks immediately.** Bronze stores raw JSON. If the Silver schema
   does not include the new field, it is silently dropped during `from_json`.
   Existing Silver jobs continue running.

2. **Schema update workflow:**
   a. Update `schemas/match_schema.py` to add the new field.
   b. Add the field to the Silver select list in the transformer.
   c. Write to Silver with `mergeSchema = True` to add the new column.
      Existing rows get NULL for the new column.
   d. If a full backfill is needed, reprocess Bronze via `_batch_id` filtering.

```python
# Silver write pattern — always use mergeSchema for incremental Silver writes
(
    participant_df
    .write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable("lol_analytics.silver.match_participants")
)

# MERGE pattern for idempotent Silver writes (prevents duplicates on reruns)
from delta.tables import DeltaTable

target = DeltaTable.forName(spark, "lol_analytics.silver.match_participants")
(
    target.alias("t")
    .merge(
        participant_df.alias("s"),
        "t.match_id = s.match_id AND t.participant_id = s.participant_id"
    )
    .withSchemaEvolution()        # DBR 15.4+ — handles new columns automatically
    .whenMatchedUpdateAll()
    .whenNotMatchedInsertAll()
    .execute()
)
```

**Use MERGE as the default Silver write pattern** — it is idempotent, handles
reruns safely, and supports `withSchemaEvolution()` for additive schema changes.

### 5.3 Breaking Schema Changes (Column Rename / Type Change)

If Riot renames a field (rare) or a type changes (e.g., int → float):

- Use `overwriteSchema = True` only for full table rebuilds.
- Coordinate with downstream Gold jobs — they must also update their column
  references before the Silver table is replaced.
- Use Unity Catalog table comments to document the change:

```sql
COMMENT ON TABLE lol_analytics.silver.match_participants IS
  'Schema v3: added chal_* challenge columns (patch 14.5). match_id + participant_id PK.';
```

**Confidence: HIGH** (official Azure Databricks docs, March 2026)

---

## 6. Unity Catalog: Lineage and Column Tagging

### 6.1 Automatic Column Lineage

Unity Catalog captures column-level lineage automatically from Spark execution
plans when tables use three-part names (`lol_analytics.silver.match_participants`).
No instrumentation is needed. The lineage graph shows:

```
bronze.match_raw.raw_json
    → silver.match_participants.champion_id  (via from_json + explode)
    → silver.match_participants.kills
    → gold.champion_stats.avg_kills  (when Gold is built)
```

Access lineage in Catalog Explorer or query system tables:
```sql
SELECT * FROM system.access.table_lineage
WHERE target_table_full_name = 'lol_analytics.silver.match_participants'
```

**Limitation:** Column-level lineage through custom Python UDFs is not tracked
at column level — only table level. Avoid UDFs in transformation pipelines
where lineage is required.

### 6.2 Column Tagging Strategy for the 147-Field Participant Table

Tag categories for `silver.match_participants`:

| Tag | Applied To | Purpose |
|-----|-----------|---------|
| `domain = "identity"` | `puuid`, `summoner_id`, `riot_id_game_name`, `riot_id_tagline` | PII governance |
| `domain = "performance"` | `kills`, `deaths`, `assists`, `total_damage_*`, `gold_*` | Core metrics |
| `domain = "vision"` | `vision_score`, `wards_placed`, `wards_killed`, `detector_wards_placed` | Vision category |
| `domain = "objectives"` | `baron_kills`, `dragon_kills`, `turret_kills`, `objectives_stolen` | Objective category |
| `domain = "challenges"` | All `chal_*` columns | Extended challenge metrics |
| `domain = "context"` | `match_id`, `team_id`, `champion_id`, `individual_position` | Join keys |
| `pii = "true"` | `puuid`, `summoner_id`, `riot_id_game_name` | PII flag for access control |

**Applying tags programmatically** (for a 147-column table, do not do this manually):

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

IDENTITY_COLS = ["puuid", "summoner_id", "riot_id_game_name", "riot_id_tagline"]

for col_name in IDENTITY_COLS:
    w.statement_execution.execute_statement(
        warehouse_id="<sql_warehouse_id>",
        statement=f"""
            ALTER TABLE lol_analytics.silver.match_participants
            ALTER COLUMN {col_name}
            SET TAGS ('domain' = 'identity', 'pii' = 'true')
        """
    )
```

**Limitation (confirmed):** ALTER TABLE SET TAGS applies to one column per
statement. For 147 columns, loop over column groups in a setup script run
once after table creation.

**Note:** Unity Catalog allows at most 1,000 column tags total per table.
With 147 columns × ~2 tags each = ~294 tags, this is well within limits.

**Confidence: HIGH** (official Azure Databricks tags docs)

### 6.3 Table Comments as Documentation

```sql
-- Run once after table creation
ALTER TABLE lol_analytics.silver.match_participants
SET TBLPROPERTIES (
  'lol.source'     = 'riot_match_v5',
  'lol.grain'      = 'one row per participant per match',
  'lol.pk'         = 'match_id + participant_id',
  'lol.queue'      = 'RANKED_SOLO_5x5',
  'lol.schema_ver' = '1'
);
```

---

## 7. Gold Layer Design Candidates

Gold layer is deferred pending Silver validation per PROJECT.md, but the
following candidates are well-justified by the Silver schema.

### 7.1 gold.champion_performance (Primary Gold Table)

**Grain:** One row per champion per position per tier per patch version.
**Source:** `silver.match_participants` + `silver.match`

```sql
CREATE OR REPLACE TABLE lol_analytics.gold.champion_performance
CLUSTER BY (champion_id, individual_position)
AS
SELECT
    mp.champion_id,
    mp.champion_name,
    mp.individual_position,
    m.game_version,
    mp._tier,
    mp._region,
    COUNT(DISTINCT mp.match_id)                         AS games_played,
    SUM(CASE WHEN mp.win THEN 1 ELSE 0 END)             AS wins,
    ROUND(AVG(mp.kills), 2)                             AS avg_kills,
    ROUND(AVG(mp.deaths), 2)                            AS avg_deaths,
    ROUND(AVG(mp.assists), 2)                           AS avg_assists,
    ROUND(AVG((mp.kills + mp.assists) /
        NULLIF(mp.deaths, 0)), 2)                       AS avg_kda,
    ROUND(AVG(mp.total_damage_dealt_to_champions), 0)   AS avg_damage_to_champs,
    ROUND(AVG(mp.gold_earned), 0)                       AS avg_gold_earned,
    ROUND(AVG(mp.vision_score), 2)                      AS avg_vision_score,
    ROUND(AVG(mp.total_minions_killed + mp.neutral_minions_killed), 1) AS avg_cs,
    ROUND(AVG(mp.chal_kill_participation), 3)           AS avg_kill_participation,
    ROUND(AVG(mp.chal_damage_per_minute), 1)            AS avg_dpm,
    ROUND(AVG(mp.chal_gold_per_minute), 1)              AS avg_gpm,
    current_timestamp()                                 AS _computed_at
FROM lol_analytics.silver.match_participants mp
JOIN lol_analytics.silver.match m
    ON mp.match_id = m.match_id
WHERE m.queue_id = 420  -- RANKED_SOLO_5x5 only
GROUP BY
    mp.champion_id, mp.champion_name, mp.individual_position,
    m.game_version, mp._tier, mp._region;
```

### 7.2 gold.pick_ban_rates

**Grain:** One row per champion per tier per patch version.
**Source:** `silver.match_participants` + `silver.match_teams_bans` + `silver.match`

```sql
-- Combine pick counts (from participants) with ban counts (from bans table)
-- to compute meta presence rate = (picks + bans) / total matches
```

### 7.3 gold.player_performance_trends

**Grain:** One row per PUUID per match — a time series of player performance.
**Source:** `silver.match_participants` + `silver.match`

Cluster on `puuid`. Enables "is this player improving?" queries for players
who appear in multiple batches.

### 7.4 gold.tier_distributions

**Grain:** One row per tier per region per ingestion batch.
**Source:** `silver.league_entries`

Simple COUNT GROUP BY used for dashboard KPIs showing ranked population breakdown.

### 7.5 gold.match_timeline_summary

**Grain:** One row per match — key aggregate stats from the timeline.
**Source:** `silver.match_timeline_participant_frames` + `silver.match_timeline_events`

Aggregates like: gold lead at 15 minutes, first dragon timestamp, first kill timestamp.
These are join keys for correlating early-game actions with match outcomes.

---

## 8. Component Boundaries

| Component | Responsibility | Input | Output |
|-----------|---------------|-------|--------|
| `bronze_ingestor.py` | Call Riot API, write raw JSON + metadata | Riot API HTTP response | `bronze.match_raw` (STRING raw_json) |
| `schemas/match_schema.py` | Own the StructType for from_json parsing | Version-controlled code | StructType object |
| `silver/match_transformer.py` | Parse, explode, flatten, write Silver | `bronze.match_raw` | All `silver.match*` tables |
| `silver/timeline_transformer.py` | Parse, explode frames/events, write Silver | `bronze.match_timeline_raw` | All `silver.match_timeline_*` tables |
| `silver/league_transformer.py` | Type and clean league entries | `bronze.league_entries` | `silver.league_entries` |
| `gold/champion_aggregator.py` | Aggregate participant data by champion | `silver.match_participants` + `silver.match` | `gold.champion_performance` |

---

## 9. Anti-Patterns to Avoid

### Anti-Pattern 1: Parsing JSON in Bronze
**What goes wrong:** Silver schema changes require reprocessing Bronze → schema drift
locks you into the ingest-time schema, losing replayability.
**Instead:** Store raw STRING in Bronze. Parse only at Silver boundary with a
version-controlled explicit StructType.

### Anti-Pattern 2: Keeping `challenges` as a STRUCT in Silver
**What goes wrong:** Gold aggregations require `challenges.kda`, `challenges.killParticipation`,
etc. Accessing nested struct fields in GROUP BY queries is verbose and breaks BI tools.
SQL users cannot discover available fields without reading schema docs.
**Instead:** Flatten all 125 challenge fields as `chal_*` prefixed columns.

### Anti-Pattern 3: Partitioning Silver tables by date
**What goes wrong:** A daily batch of 200 Challenger players generates far fewer than
1 GB per partition. Databricks performance degrades with tiny partitions, causing
excessive metadata reads and poor file consolidation.
**Instead:** Use Liquid Clustering. No partitions. Let ingestion-time clustering handle layout.

### Anti-Pattern 4: Using `inferSchema = True` or `schema_of_json` in production
**What goes wrong:** `schema_of_json` infers from a single sample row. It can produce
incorrect nullable/non-nullable judgments, miss fields that appear in only some matches
(e.g., `tournamentCode`), and change behavior across Spark versions.
**Instead:** Define the schema explicitly in `schemas/match_schema.py` and control
schema evolution through version control.

### Anti-Pattern 5: Global `spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", True)`
**What goes wrong:** Session-wide schema evolution causes unintended schema changes
across unrelated write operations in the same job.
**Instead:** Use `MERGE WITH SCHEMA EVOLUTION` or `.option("mergeSchema", "true")`
per-operation only.

### Anti-Pattern 6: Using `explode()` on array-of-struct when `inline()` is available
**What goes wrong:** `explode()` produces one struct column requiring a second select
to unpack fields. Two Spark stages instead of one, more code, harder to read.
**Instead:** Use `inline()` or `inline_outer()` for `bans[]` and similar bounded
array-of-struct fields where all elements share the same schema.

---

## 10. Sources

- [When to partition tables on Azure Databricks](https://learn.microsoft.com/en-us/azure/databricks/tables/partitions) — March 2026
- [Use liquid clustering for tables — Azure Databricks](https://learn.microsoft.com/en-us/azure/databricks/delta/clustering) — March 2026
- [Update table schema — Azure Databricks (mergeSchema, MERGE WITH SCHEMA EVOLUTION)](https://learn.microsoft.com/en-us/azure/databricks/delta/update-schema) — March 2026
- [Apply tags to Unity Catalog securable objects](https://learn.microsoft.com/en-us/azure/databricks/database-objects/tags)
- [View data lineage using Unity Catalog](https://learn.microsoft.com/en-us/azure/databricks/data-governance/unity-catalog/data-lineage)
- [PySpark inline function docs](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.inline.html)
- [PySpark explode function docs](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.explode.html)
- [Delta Lake best practices — Azure Databricks](https://learn.microsoft.com/en-us/azure/databricks/delta/best-practices)
