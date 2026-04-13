"""
Ingest Summoner-V4 profiles for each PUUID in bronze.league_entries not yet in
bronze.summoner_raw.

ROUTING: Summoner-V4 uses PLATFORM routing — get_platform_host(), NOT get_region_host().
For KR: kr.api.riotgames.com (correct) vs asia.api.riotgames.com (WRONG — returns 404).

API: GET https://{platform_host}/lol/summoner/v4/summoners/by-puuid/{encryptedPUUID}

MERGE key: puuid
Table: lol_analytics.bronze.summoner_raw — USING DELTA, UC three-part name (BRZ-10).
"""
import uuid
import json
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_platform_host
from src.common.logger import get_logger

logger = get_logger(__name__)


def ingest_summoner(
    spark: SparkSession,
    limiter: RiotRateLimiter,
    api_key: str,
    region: str,
    tier: str,
    batch_id: str | None = None,
) -> dict:
    """Fetch summoner profiles for all new PUUIDs and MERGE into bronze.summoner_raw.

    Returns: {"requests_made": int, "count_429": int, "new_rows": int}
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4())

    platform_host = get_platform_host(region)   # PLATFORM routing — Summoner-V4
    headers = {"X-Riot-Token": api_key}

    spark.sql("""
        CREATE TABLE IF NOT EXISTS lol_analytics.bronze.summoner_raw (
            puuid          STRING,
            raw_json       STRING,
            _region        STRING,
            _batch_id      STRING,
            _ingested_at   TIMESTAMP,
            _source_url    STRING
        ) USING DELTA
    """)

    # Anti-join: PUUIDs in league_entries not yet in summoner_raw
    new_puuids_df = spark.sql(f"""
        SELECT DISTINCT a.puuid
        FROM lol_analytics.bronze.league_entries AS a
        LEFT ANTI JOIN lol_analytics.bronze.summoner_raw AS b
        ON a.puuid = b.puuid
        WHERE a._region = '{region}' AND a._tier = '{tier}'
    """)
    new_puuids = [row["puuid"] for row in new_puuids_df.collect()]
    logger.info(f"summoner: {len(new_puuids)} new PUUIDs to fetch")

    rows = []
    requests_made = 0
    count_429 = 0
    ingested_at = datetime.now(timezone.utc)

    for puuid in new_puuids:
        url = f"https://{platform_host}/lol/summoner/v4/summoners/by-puuid/{puuid}"
        try:
            summoner_data = call_riot_api(url, headers, limiter)
            requests_made += 1
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                count_429 += 1
            raise

        rows.append({
            "puuid":        summoner_data.get("puuid", puuid),
            "raw_json":     json.dumps(summoner_data),
            "_region":      region,
            "_batch_id":    batch_id,
            "_ingested_at": ingested_at,
            "_source_url":  url,
        })

    if rows:
        df = spark.createDataFrame(rows)
        df.createOrReplaceTempView("_staging_summoner")
        result = spark.sql("""
            MERGE INTO lol_analytics.bronze.summoner_raw AS target
            USING _staging_summoner AS source
            ON target.puuid = source.puuid
            WHEN NOT MATCHED THEN INSERT *
        """)
        new_rows = result.first()["num_inserted_rows"] if result else 0
    else:
        new_rows = 0

    logger.info(f"summoner: {requests_made} requests, {new_rows} new rows merged")
    return {"requests_made": requests_made, "count_429": count_429, "new_rows": new_rows}
