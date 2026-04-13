"""
Ingest Match-V5 match IDs for each PUUID in bronze.league_entries.

API: GET https://{region_host}/lol/match/v5/matches/by-puuid/{puuid}/ids
     ?queue=420&start=0&count=20

MERGE key: (puuid, match_id) — idempotent on re-run.
Table: lol_analytics.bronze.match_ids — USING DELTA, UC three-part name (BRZ-10).
"""
import uuid
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_region_host, DEFAULT_MATCH_COUNT
from src.common.logger import get_logger

logger = get_logger(__name__)


def ingest_match_ids(
    spark: SparkSession,
    limiter: RiotRateLimiter,
    api_key: str,
    region: str,
    tier: str,
    batch_id: str | None = None,
) -> dict:
    """Fetch match IDs for all PUUIDs in league_entries and MERGE into bronze.match_ids.

    Returns: {"requests_made": int, "count_429": int, "new_rows": int}
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4())

    region_host = get_region_host(region)
    headers = {"X-Riot-Token": api_key}

    spark.sql("""
        CREATE TABLE IF NOT EXISTS lol_analytics.bronze.match_ids (
            puuid          STRING,
            match_id       STRING,
            _region        STRING,
            _tier          STRING,
            _batch_id      STRING,
            _ingested_at   TIMESTAMP
        ) USING DELTA
    """)

    # Read all PUUIDs for this region/tier from league_entries
    puuids_df = spark.sql(
        f"SELECT DISTINCT puuid FROM lol_analytics.bronze.league_entries "
        f"WHERE _region = '{region}' AND _tier = '{tier}'"
    )
    puuids = [row["puuid"] for row in puuids_df.collect()]
    logger.info(f"match_ids: processing {len(puuids)} PUUIDs for region={region} tier={tier}")

    rows = []
    requests_made = 0
    count_429 = 0
    ingested_at = datetime.now(timezone.utc)

    for puuid in puuids:
        url = (
            f"https://{region_host}/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?queue=420&start=0&count={DEFAULT_MATCH_COUNT}"
        )
        try:
            match_ids = call_riot_api(url, headers, limiter)
            requests_made += 1
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                count_429 += 1
            raise

        for match_id in match_ids:
            rows.append({
                "puuid":        puuid,
                "match_id":     match_id,
                "_region":      region,
                "_tier":        tier,
                "_batch_id":    batch_id,
                "_ingested_at": ingested_at,
            })

    if rows:
        df = spark.createDataFrame(rows)
        df.createOrReplaceTempView("_staging_match_ids")
        result = spark.sql("""
            MERGE INTO lol_analytics.bronze.match_ids AS target
            USING _staging_match_ids AS source
            ON target.puuid = source.puuid AND target.match_id = source.match_id
            WHEN NOT MATCHED THEN INSERT *
        """)
        new_rows = result.first()["num_inserted_rows"] if result else 0
    else:
        new_rows = 0

    logger.info(f"match_ids: {requests_made} requests, {new_rows} new rows merged")
    return {"requests_made": requests_made, "count_429": count_429, "new_rows": new_rows}
