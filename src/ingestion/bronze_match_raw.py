"""
Ingest Match-V5 full match details for each new match_id not yet in bronze.match_raw.

Anti-join pre-check: reads match_ids NOT in match_raw — avoids wasting API quota
on already-ingested matches (implements D-02: restart-clean with MERGE dedup).

API: GET https://{region_host}/lol/match/v5/matches/{matchId}

MERGE key: match_id — idempotent on re-run.
Table: lol_analytics.bronze.match_raw — USING DELTA, UC three-part name (BRZ-10).
"""
import uuid
import json
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_region_host
from src.common.logger import get_logger

logger = get_logger(__name__)


def ingest_match_raw(
    spark: SparkSession,
    limiter: RiotRateLimiter,
    api_key: str,
    region: str,
    batch_id: str | None = None,
) -> dict:
    """Fetch match details for all new match_ids and MERGE into bronze.match_raw.

    Uses anti-join against match_raw to skip already-ingested matches.
    Returns: {"requests_made": int, "count_429": int, "new_rows": int}
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4())

    region_host = get_region_host(region)
    headers = {"X-Riot-Token": api_key}

    spark.sql("""
        CREATE TABLE IF NOT EXISTS lol_analytics.bronze.match_raw (
            match_id        STRING,
            raw_json        STRING,
            platform_id     STRING,
            game_creation   BIGINT,
            _batch_id       STRING,
            _ingested_at    TIMESTAMP,
            _source_url     STRING
        ) USING DELTA
    """)

    # Anti-join: match IDs in match_ids but NOT yet in match_raw
    new_ids_df = spark.sql("""
        SELECT DISTINCT a.match_id
        FROM lol_analytics.bronze.match_ids AS a
        LEFT ANTI JOIN lol_analytics.bronze.match_raw AS b
        ON a.match_id = b.match_id
    """)
    new_match_ids = [row["match_id"] for row in new_ids_df.collect()]
    logger.info(f"match_raw: {len(new_match_ids)} new match IDs to fetch (anti-join result)")

    rows = []
    requests_made = 0
    count_429 = 0
    ingested_at = datetime.now(timezone.utc)

    for match_id in new_match_ids:
        url = f"https://{region_host}/lol/match/v5/matches/{match_id}"
        try:
            match_data = call_riot_api(url, headers, limiter)
            requests_made += 1
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                count_429 += 1
            raise

        rows.append({
            "match_id":      match_data.get("metadata", {}).get("matchId", match_id),
            "raw_json":      json.dumps(match_data),
            "platform_id":   match_data.get("info", {}).get("platformId"),
            "game_creation": match_data.get("info", {}).get("gameCreation"),
            "_batch_id":     batch_id,
            "_ingested_at":  ingested_at,
            "_source_url":   url,
        })

    if rows:
        df = spark.createDataFrame(rows)
        df.createOrReplaceTempView("_staging_match_raw")
        result = spark.sql("""
            MERGE INTO lol_analytics.bronze.match_raw AS target
            USING _staging_match_raw AS source
            ON target.match_id = source.match_id
            WHEN NOT MATCHED THEN INSERT *
        """)
        new_rows = result.first()["num_inserted_rows"] if result else 0
    else:
        new_rows = 0

    logger.info(f"match_raw: {requests_made} requests, {new_rows} new rows merged")
    return {"requests_made": requests_made, "count_429": count_429, "new_rows": new_rows}
