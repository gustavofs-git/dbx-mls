# Databricks notebook source
# MAGIC %md
# MAGIC # Smoke Test — dbx-mls Infrastructure Health Check
# MAGIC
# MAGIC Validates three things on every dev deploy:
# MAGIC 1. Riot API key retrievable from Databricks Secret Scope (value auto-redacted in logs)
# MAGIC 2. Unity Catalog `lol_analytics` schemas accessible from job cluster
# MAGIC 3. Bronze table roundtrip: create → read → drop `lol_analytics.bronze.smoke_test`
# MAGIC
# MAGIC **This notebook is permanent.** It runs after every `cd-dev.yml` deploy as an infra health check.
# MAGIC Per D-04: this job is NEVER removed after Phase 1 — it serves as an ongoing infrastructure health-check.

# COMMAND ----------

import sys

print("=" * 60)
print("dbx-mls Smoke Test — starting")
print("=" * 60)

# COMMAND ----------

# Validation 1: Riot API key retrievable from secret scope
# Databricks automatically redacts the value in notebook and job logs
print("\n--- Validation 1: Databricks Secrets ---")
try:
    api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
    assert len(api_key) > 0, "riot-api-key returned an empty string — check secret value"
    print("Validation 1 PASSED: Riot API key retrieved (value redacted in logs)")
except Exception as e:
    print(f"Validation 1 FAILED: {e}", file=sys.stderr)
    raise

# COMMAND ----------

# Validation 2: Unity Catalog lol_analytics schemas accessible
print("\n--- Validation 2: Unity Catalog Access ---")
try:
    schemas_df = spark.sql("SHOW SCHEMAS IN lol_analytics")
    schema_names = [row["databaseName"] for row in schemas_df.collect()]
    assert "bronze" in schema_names, f"bronze schema not found. Got: {schema_names}"
    assert "silver" in schema_names, f"silver schema not found. Got: {schema_names}"
    assert "gold" in schema_names, f"gold schema not found. Got: {schema_names}"
    print(f"Validation 2 PASSED: UC schemas confirmed: {schema_names}")
except Exception as e:
    print(f"Validation 2 FAILED: {e}", file=sys.stderr)
    raise

# COMMAND ----------

# Validation 3: Bronze table roundtrip (create → insert → read → drop)
print("\n--- Validation 3: Bronze Table Roundtrip ---")
try:
    spark.sql("DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test")
    spark.sql(
        "CREATE TABLE lol_analytics.bronze.smoke_test "
        "(id BIGINT, msg STRING) "
        "USING DELTA"
    )
    spark.sql("INSERT INTO lol_analytics.bronze.smoke_test VALUES (1, 'smoke')")
    result = spark.sql(
        "SELECT COUNT(*) as cnt FROM lol_analytics.bronze.smoke_test"
    ).collect()[0]["cnt"]
    assert result >= 1, f"Expected at least 1 row, got {result}"
    spark.sql("DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test")
    print("Validation 3 PASSED: Bronze table roundtrip (create/read/drop) succeeded")
except Exception as e:
    spark.sql("DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test")
    print(f"Validation 3 FAILED: {e}", file=sys.stderr)
    raise

# COMMAND ----------

print("\n" + "=" * 60)
print("SMOKE TEST PASSED")
print("=" * 60)
