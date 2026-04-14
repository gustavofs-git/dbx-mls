# Databricks notebook source
# COMMAND ----------
import os, sys
# __file__ is not defined in Databricks notebook execution context.
# In Git-source DAB jobs, cwd is set to the repo root — use that directly.
_repo_root = os.getcwd()
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# COMMAND ----------
import uuid
from datetime import datetime, timezone

from src.riot_client import RiotRateLimiter
from src.config import get_job_params
from src.ingestion.bronze_match_raw import ingest_match_raw
from src.common.logger import get_logger

logger = get_logger("notebook.ingest_match_raw")

# COMMAND ----------
params = get_job_params(dbutils)
region = params["region"]
api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
batch_id = str(uuid.uuid4())

run_start = datetime.now(timezone.utc)
limiter = RiotRateLimiter()
result = ingest_match_raw(spark, limiter, api_key, region, batch_id=batch_id)
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
logger.info(f"match_raw DONE: {result}")
