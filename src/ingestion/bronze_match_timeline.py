"""
Ingest Match-V5 timeline data for each match_id in bronze.match_raw not yet in
bronze.match_timeline_raw.

Timeline is large JSON (~28 frames × 10 participants). Runs as a separate DAB task —
failure here does NOT block match detail ingestion or summoner/account tasks.

API: GET https://{region_host}/lol/match/v5/matches/{matchId}/timeline
Routing: REGIONAL host (asia.api.riotgames.com for KR) — same as Match-V5

MERGE key: match_id
Table: lol_analytics.bronze.match_timeline_raw — USING DELTA, UC three-part name (BRZ-10).
"""
import uuid
import json
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_region_host
from src.common.logger import get_logger

logger = get_logger(__name__)


def ingest_match_timeline(
    spark: SparkSession,
    limiter: RiotRateLimiter,
    api_key: str,
    region: str,
    batch_id: str | None = None,
) -> dict:
    """Fetch timeline for all match_ids in match_raw not yet in match_timeline_raw.

    Returns: {"requests_made": int, "count_429": int, "new_rows": int}
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4())

    region_host = get_region_host(region)
    headers = {"X-Riot-Token": api_key}

    spark.sql("""
        CREATE TABLE IF NOT EXISTS lol_analytics.bronze.match_timeline_raw (
            match_id       STRING,
            raw_json       STRING,
            _batch_id      STRING,
            _ingested_at   TIMESTAMP,
            _source_url    STRING
        ) USING DELTA
    """)

    # Anti-join: match_ids in match_raw but NOT yet in match_timeline_raw
    new_ids_df = spark.sql("""
        SELECT DISTINCT a.match_id
        FROM lol_analytics.bronze.match_raw AS a
        LEFT ANTI JOIN lol_analytics.bronze.match_timeline_raw AS b
        ON a.match_id = b.match_id
    """)
    new_match_ids = [row["match_id"] for row in new_ids_df.collect()]
    logger.info(f"match_timeline: {len(new_match_ids)} new match IDs to fetch")

    rows = []
    requests_made = 0
    count_429 = 0
    ingested_at = datetime.now(timezone.utc)

    for match_id in new_match_ids:
        url = f"https://{region_host}/lol/match/v5/matches/{match_id}/timeline"
        try:
            timeline_data = call_riot_api(url, headers, limiter)
            requests_made += 1
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                count_429 += 1
            raise

        rows.append({
            "match_id":     match_id,
            "raw_json":     json.dumps(timeline_data),
            "_batch_id":    batch_id,
            "_ingested_at": ingested_at,
            "_source_url":  url,
        })

    if rows:
        df = spark.createDataFrame(rows)
        df.createOrReplaceTempView("_staging_match_timeline")
        result = spark.sql("""
            MERGE INTO lol_analytics.bronze.match_timeline_raw AS target
            USING _staging_match_timeline AS source
            ON target.match_id = source.match_id
            WHEN NOT MATCHED THEN INSERT *
        """)
        new_rows = result.first()["num_inserted_rows"] if result else 0
    else:
        new_rows = 0

    logger.info(f"match_timeline: {requests_made} requests, {new_rows} new rows merged")
    return {"requests_made": requests_made, "count_429": count_429, "new_rows": new_rows}
