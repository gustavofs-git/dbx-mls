# Databricks notebook source
# COMMAND ----------
import os, sys
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# COMMAND ----------
import uuid
from datetime import datetime, timezone

from src.riot_client import RiotRateLimiter
from src.config import get_job_params
from src.ingestion.bronze_summoner import ingest_summoner
from src.common.logger import get_logger

logger = get_logger("notebook.ingest_summoner")

# COMMAND ----------
params = get_job_params(dbutils)
region = params["region"]
tier = params["tier"]
api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
batch_id = str(uuid.uuid4())

run_start = datetime.now(timezone.utc)
limiter = RiotRateLimiter()
result = ingest_summoner(spark, limiter, api_key, region, tier, batch_id=batch_id)
run_end = datetime.now(timezone.utc)

# COMMAND ----------
from pyspark.sql import Row
log_row = spark.createDataFrame([Row(
    batch_id=batch_id,
    run_start=run_start,
    run_end=run_end,
    requests_made=result["requests_made"],
    count_429=result["count_429"],
    new_matches_ingested=result["new_rows"],
    status="SUCCESS",
)])
log_row.write.mode("append").saveAsTable("lol_analytics.bronze.ingestion_log")
logger.info(f"summoner DONE: {result}")
