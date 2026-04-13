"""
Ingest League-Exp-V4 Challenger/Grandmaster/Master entries into bronze.league_entries.

API: GET https://{platform_host}/lol/league-exp/v4/entries/{queue}/{tier}/{division}
     ?page=1,2,... until empty response list

MERGE key: (puuid, _region, _tier) — idempotent on re-run.
Table: lol_analytics.bronze.league_entries — USING DELTA, UC three-part name (BRZ-10).
"""
import uuid
import json
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_platform_host, RANKED_QUEUE
from src.common.logger import get_logger

logger = get_logger(__name__)


def ingest_league_entries(
    spark: SparkSession,
    limiter: RiotRateLimiter,
    api_key: str,
    region: str,
    tier: str,
    batch_id: str | None = None,
) -> dict:
    """Fetch all League-Exp-V4 entries for (region, tier) and MERGE into bronze.league_entries.

    Returns a dict with: {"requests_made": int, "count_429": int, "new_rows": int}
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4())

    platform_host = get_platform_host(region)
    headers = {"X-Riot-Token": api_key}

    spark.sql("""
        CREATE TABLE IF NOT EXISTS lol_analytics.bronze.league_entries (
            summonerId     STRING,
            leagueId       STRING,
            queueType      STRING,
            tier           STRING,
            rank           STRING,
            leaguePoints   BIGINT,
            wins           BIGINT,
            losses         BIGINT,
            veteran        BOOLEAN,
            inactive       BOOLEAN,
            freshBlood     BOOLEAN,
            hotStreak      BOOLEAN,
            puuid          STRING,
            _raw_json      STRING,
            _region        STRING,
            _tier          STRING,
            _page          BIGINT,
            _batch_id      STRING,
            _ingested_at   TIMESTAMP,
            _source_url    STRING
        ) USING DELTA
    """)

    rows = []
    requests_made = 0
    count_429 = 0
    page = 1

    ingested_at = datetime.now(timezone.utc)

    while True:
        url = (
            f"https://{platform_host}/lol/league-exp/v4/entries"
            f"/{RANKED_QUEUE}/{tier}/I?page={page}"
        )
        source_url = url  # no API key in stored URL

        try:
            entries = call_riot_api(url, headers, limiter)
            requests_made += 1
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                count_429 += 1
            raise

        if not entries:
            logger.info(f"league_entries: empty page {page} — pagination complete")
            break

        for entry in entries:
            rows.append({
                "summonerId":   entry.get("summonerId"),
                "leagueId":     entry.get("leagueId"),
                "queueType":    entry.get("queueType"),
                "tier":         entry.get("tier"),
                "rank":         entry.get("rank"),
                "leaguePoints": entry.get("leaguePoints"),
                "wins":         entry.get("wins"),
                "losses":       entry.get("losses"),
                "veteran":      entry.get("veteran"),
                "inactive":     entry.get("inactive"),
                "freshBlood":   entry.get("freshBlood"),
                "hotStreak":    entry.get("hotStreak"),
                "puuid":        entry.get("puuid"),
                "_raw_json":    json.dumps(entry),
                "_region":      region,
                "_tier":        tier,
                "_page":        page,
                "_batch_id":    batch_id,
                "_ingested_at": ingested_at,
                "_source_url":  source_url,
            })

        logger.info(f"league_entries: fetched page {page}, {len(entries)} entries")
        page += 1

    if rows:
        df = spark.createDataFrame(rows)
        df.createOrReplaceTempView("_staging_league_entries")
        result = spark.sql("""
            MERGE INTO lol_analytics.bronze.league_entries AS target
            USING _staging_league_entries AS source
            ON target.puuid = source.puuid
               AND target._region = source._region
               AND target._tier = source._tier
            WHEN NOT MATCHED THEN INSERT *
        """)
        new_rows = result.first()["num_inserted_rows"] if result else 0
    else:
        new_rows = 0

    logger.info(
        f"league_entries: {requests_made} requests, {new_rows} new rows merged, "
        f"region={region} tier={tier}"
    )
    return {"requests_made": requests_made, "count_429": count_429, "new_rows": new_rows}
