"""
Ingest Account-V1 account details for each PUUID in bronze.league_entries not yet in
bronze.account_raw.

ROUTING: Account-V1 uses REGIONAL routing — get_region_host(), NOT get_platform_host().
For KR: asia.api.riotgames.com (correct) vs kr.api.riotgames.com (WRONG — returns 404).

API: GET https://{region_host}/riot/account/v1/accounts/by-puuid/{puuid}

MERGE key: puuid
Table: lol_analytics.bronze.account_raw — USING DELTA, UC three-part name (BRZ-10).
"""
import uuid
import json
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_region_host
from src.common.logger import get_logger

logger = get_logger(__name__)


def ingest_account(
    spark: SparkSession,
    limiter: RiotRateLimiter,
    api_key: str,
    region: str,
    tier: str,
    batch_id: str | None = None,
) -> dict:
    """Fetch account details for all new PUUIDs and MERGE into bronze.account_raw.

    Returns: {"requests_made": int, "count_429": int, "new_rows": int}
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4())

    region_host = get_region_host(region)   # REGIONAL routing — Account-V1
    headers = {"X-Riot-Token": api_key}

    spark.sql("""
        CREATE TABLE IF NOT EXISTS lol_analytics.bronze.account_raw (
            puuid          STRING,
            raw_json       STRING,
            _region        STRING,
            _batch_id      STRING,
            _ingested_at   TIMESTAMP,
            _source_url    STRING
        ) USING DELTA
    """)

    # Anti-join: PUUIDs in league_entries not yet in account_raw
    new_puuids_df = spark.sql(f"""
        SELECT DISTINCT a.puuid
        FROM lol_analytics.bronze.league_entries AS a
        LEFT ANTI JOIN lol_analytics.bronze.account_raw AS b
        ON a.puuid = b.puuid
        WHERE a._region = '{region}' AND a._tier = '{tier}'
    """)
    new_puuids = [row["puuid"] for row in new_puuids_df.collect()]
    logger.info(f"account: {len(new_puuids)} new PUUIDs to fetch")

    rows = []
    requests_made = 0
    count_429 = 0
    ingested_at = datetime.now(timezone.utc)

    for puuid in new_puuids:
        url = f"https://{region_host}/riot/account/v1/accounts/by-puuid/{puuid}"
        try:
            account_data = call_riot_api(url, headers, limiter)
            requests_made += 1
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                count_429 += 1
            raise

        rows.append({
            "puuid":        account_data.get("puuid", puuid),
            "raw_json":     json.dumps(account_data),
            "_region":      region,
            "_batch_id":    batch_id,
            "_ingested_at": ingested_at,
            "_source_url":  url,
        })

    if rows:
        df = spark.createDataFrame(rows)
        df.createOrReplaceTempView("_staging_account")
        result = spark.sql("""
            MERGE INTO lol_analytics.bronze.account_raw AS target
            USING _staging_account AS source
            ON target.puuid = source.puuid
            WHEN NOT MATCHED THEN INSERT *
        """)
        new_rows = result.first()["num_inserted_rows"] if result else 0
    else:
        new_rows = 0

    logger.info(f"account: {requests_made} requests, {new_rows} new rows merged")
    return {"requests_made": requests_made, "count_429": count_429, "new_rows": new_rows}
