# Phase 2: Bronze Ingestion Pipeline - Research

**Researched:** 2026-04-13
**Domain:** Riot Games API ingestion, Python rate limiting, Delta MERGE deduplication, Databricks Asset Bundles job DAG
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** All API calls execute in plain Python `for` loops on the Spark driver — no
  Spark-distributed fetch, no `mapPartitions`, no worker-side HTTP calls. The dual-bucket
  rate limiter singleton is shared naturally within the driver process. Spark is used for
  Delta writes only.

- **D-02:** Restart-clean, rely on MERGE deduplication. If the job dies mid-run, the next
  run starts from the beginning of the chain. MERGE idempotency (dedup on primary keys) and
  the anti-join pre-check (`bronze.match_ids` vs `bronze.match_raw`) mean re-running wastes
  zero API calls on already-ingested matches. No checkpoint file, no resume-from-offset
  logic.

- **D-03:** LinkedIn article format: full-story technical deep-dive with real code snippets,
  covering the complete Phase 2 scope as one coherent narrative. Short post + detailed article
  pair.

- **D-04:** Article MUST be written AFTER human acceptance testing (UAT) passes. Real pipeline
  results (actual row counts from `SELECT COUNT(*) FROM lol_analytics.bronze.match_raw`) must
  be incorporated before commit. The article is a post-UAT deliverable, not pre-testing.

- **D-05:** Article generated in English first, then LPH agent humanizes and translates to
  Brazilian Portuguese — same workflow as Phase 1.

- **D-06:** Use the 7-field `ingestion_log` schema exactly:
  `(batch_id, run_start, run_end, requests_made, count_429, new_matches_ingested, status)`.
  No per-endpoint breakdowns, no `error_message` column.

### Claude's Discretion

- Exact `ingestion_log` Delta table properties (partitioning, clustering)
- Python package structure within `src/` (whether `__init__.py` files are needed for pytest
  import resolution — follow whatever pattern makes `pytest tests/unit/` work locally)
- Logging verbosity levels and exact log message formats in `src/common/logger.py`
- Order of SQL columns in CREATE TABLE / MERGE statements (schema consistency over aesthetics)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 2 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BRZ-01 | `RiotApiClient` class in `src/riot_client.py` with dual-bucket rate limiter (20 req/sec + 100 req/2min) and `Retry-After` header parsing | Token bucket algorithm pattern; `requests` + `time.monotonic()` implementation |
| BRZ-02 | Region and Tier are DAB job parameters (`region`, `tier`) — never hardcoded | `dbutils.widgets.get()` at job runtime; validated in `get_job_params()` |
| BRZ-03 | Platform-to-routing-host mapping for all 17 Riot platforms in `src/config.py` | Complete mapping defined in ROADMAP.md Plan 02-02 |
| BRZ-04 | `bronze.league_entries` populated from League-Exp-V4 with MERGE dedup on `(puuid, _region, _tier)` | Paginate until empty page; raw JSON STRING + metadata columns |
| BRZ-05 | `bronze.match_ids` populated from Match-V5 by-puuid with MERGE on `(puuid, match_id)` | Anti-join dedup pattern established in ROADMAP.md |
| BRZ-06 | `bronze.match_raw` populated from Match-V5 detail with MERGE on `match_id` | Pre-check anti-join vs match_ids; full JSON as STRING |
| BRZ-07 | `bronze.match_timeline_raw` — separate DAB task, independent failure boundary | Anti-join dedup on `match_id`; timeline is ~28 frames, large JSON |
| BRZ-08 | `bronze.summoner_raw` from Summoner-V4 by PUUID — PLATFORM routing | MERGE on `puuid`; `kr.api.riotgames.com` for KR platform |
| BRZ-09 | `bronze.account_raw` from Account-V1 by PUUID — REGIONAL routing | MERGE on `puuid`; `asia.api.riotgames.com` for KR region |
| BRZ-10 (implicit) | All Bronze tables: Delta format, UC three-part names, no DBFS, no Hive Metastore | Established constraint from Phase 1; enforced by `lol_analytics.bronze.*` naming |
| TEST-02 | Unit tests for `RiotApiClient` rate limiter logic (mocked HTTP responses) | `pytest-mock` already in requirements-dev.txt; no live API key needed |
| TEST-04 | `pytest` runs locally on Linux without a live Databricks cluster (Java 11 required) | Java 11 available via apt but NOT currently installed — see Environment section |
</phase_requirements>

---

## Summary

Phase 2 builds the full Bronze ingestion pipeline on top of the Phase 1 infrastructure. The
work is well-scoped in ROADMAP.md with exact deliverables, class names, method signatures, and
table schemas already defined. All architectural decisions are locked (driver-side loops, MERGE
dedup, no checkpointing). The main technical challenge is the dual-bucket token bucket rate
limiter and the correct Riot API routing separation (platform vs. regional host).

The existing project stack (`requests>=2.32.0`, `tenacity>=9.0.0`, `pytest-mock`, `pyspark`,
`delta-spark`) covers all Phase 2 needs. The DAB job pattern (cluster config, `source: GIT`,
`SINGLE_USER` mode) is directly reusable from the smoke test job. The `src/` directory is
completely empty — all new modules land with no conflicts.

The critical environmental gap is Java: `pyspark` local mode requires Java 11, and Java is
not currently installed or on `JAVA_HOME`. Plan 02-05 must include a Wave 0 step to install
`openjdk-11-jdk-headless` and set `JAVA_HOME`.

**Primary recommendation:** Follow the ROADMAP.md plan definitions exactly — they are
prescriptive enough to implement directly. Focus research energy on the token bucket rate
limiter pattern and Riot API routing subtleties, which are the two areas most likely to cause
bugs if implemented naively.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | >=2.32.0 | HTTP client for Riot API calls | Already in `requirements.txt`; synchronous, widely understood, fits driver-side loop model |
| `pyspark` | 3.5.3 | Delta table writes from driver | Already in `requirements-dev.txt`; matches DBR 16.4 LTS Spark version |
| `delta-spark` | 3.3.2 | Local Delta reads in tests | Already in `requirements-dev.txt` |
| `pytest` | >=8.3.0 | Test runner | Already in `requirements-dev.txt` |
| `pytest-mock` | >=3.14.0 | Mock `requests.get` and `time.sleep` | Already in `requirements-dev.txt` |
| `tenacity` | >=9.0.0 | Available for retry logic | Already in `requirements.txt` — but ROADMAP specifies manual retry loop for 429, not tenacity decorator. Use tenacity only if explicit retry decoration is desired. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `chispa` | >=0.9.4 | DataFrame equality assertions | Use in any test comparing Spark DataFrames (not needed for rate limiter unit tests) |
| `uuid` | stdlib | Generate `_batch_id` per run | Use `uuid.uuid4()` in ingestion modules; no install needed |
| `time` | stdlib | `time.monotonic()` for token bucket refill | Core of `RiotRateLimiter` — no install needed |
| `logging` / `json` | stdlib | Structured JSON logging to stdout | Used in `src/common/logger.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` (sync) | `httpx` (async) | Decision D-01 locks in sync; asyncio would break singleton limiter sharing |
| `time.monotonic()` for bucket | `tenacity` retry decorator | ROADMAP specifies manual 429 handling with `Retry-After` parsing — tenacity doesn't expose `X-Rate-Limit-Type` header |
| Manual token bucket | `pyrate_limiter` | Custom gives exact 20/sec + 100/2min dual-bucket; pyrate_limiter adds dependency without solving routing-specific `Retry-After` logic |

**Installation:** No new packages needed — all required packages already in `requirements.txt`
and `requirements-dev.txt`.

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── __init__.py              # empty — enables `import src.riot_client` in tests
├── riot_client.py           # RiotRateLimiter + call_riot_api() + RiotApiError
├── config.py                # PLATFORM_TO_REGION, get_platform_host(), get_region_host(), get_job_params()
├── common/
│   ├── __init__.py          # empty
│   ├── logger.py            # get_logger() returning JSON-formatted logger
│   └── exceptions.py        # RiotApiError, RateLimitError, ConfigError
└── ingestion/
    ├── __init__.py          # empty
    ├── bronze_league_entries.py
    ├── bronze_match_ids.py
    ├── bronze_match_raw.py
    ├── bronze_match_timeline.py
    ├── bronze_summoner.py
    └── bronze_account.py

notebooks/
├── smoke_test.py            # existing — do not modify
├── ingest_league_entries.py # DAB notebook task for Plan 02-03
├── ingest_match_ids.py
├── ingest_match_raw.py
├── ingest_match_timeline.py
├── ingest_summoner.py
└── ingest_account.py

resources/jobs/
├── smoke_test_job.yml       # existing
├── ingestion_job.yml        # replace placeholder with full 5-task DAG
└── transformation_job.yml   # existing placeholder — do not modify

tests/unit/
├── test_placeholder.py      # existing — keep
├── test_riot_client.py      # Plan 02-05
└── test_config.py           # Plan 02-05
```

**`__init__.py` decision:** pytest `testpaths = tests/unit` with `src/` as a plain directory
(no install) requires either `__init__.py` files or `conftest.py` with `sys.path` manipulation.
The cleanest approach for this repo is empty `__init__.py` in each `src/` package — no
`conftest.py` hacks needed, and it matches the `pytest tests/unit/ --cov=src` CI command.

### Pattern 1: Dual-Bucket Token Bucket Rate Limiter

**What:** A class that tracks two independent token buckets — one for 20 req/sec and one for
100 req/2min. `acquire()` blocks until both buckets have a token available. Refill uses
`time.monotonic()` to compute elapsed time since last refill and add proportional tokens.

**When to use:** Before every `requests.get()` call in `call_riot_api()`.

**Example:**
```python
# Source: standard token bucket algorithm adapted for Riot API dual-bucket constraint
import time
import threading

class RiotRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        # Bucket 1: 20 req/sec
        self._sec_tokens = 20
        self._sec_capacity = 20
        self._sec_refill_rate = 20.0  # tokens per second
        # Bucket 2: 100 req/2min
        self._min_tokens = 100
        self._min_capacity = 100
        self._min_refill_rate = 100 / 120.0  # tokens per second
        self._last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._sec_tokens = min(self._sec_capacity,
                               self._sec_tokens + elapsed * self._sec_refill_rate)
        self._min_tokens = min(self._min_capacity,
                               self._min_tokens + elapsed * self._min_refill_rate)

    def acquire(self):
        while True:
            with self._lock:
                self._refill()
                if self._sec_tokens >= 1 and self._min_tokens >= 1:
                    self._sec_tokens -= 1
                    self._min_tokens -= 1
                    return
            time.sleep(0.05)  # release lock between checks (NOT as primary throttle)
```

**Key distinction:** `time.sleep(0.05)` here is a lock-release wait between bucket-check
attempts, NOT the primary throttle. The ROADMAP explicitly forbids using `sleep(0.05)` as
the primary throttle. The token bucket IS the throttle.

### Pattern 2: 429 Handling with `Retry-After`

**What:** After a 429 response, read `X-Rate-Limit-Type` header to distinguish application/method
limits (sleep `Retry-After` seconds, then retry) from service limits (exponential backoff with
jitter).

**Example:**
```python
# Source: Riot API Developer documentation pattern
def call_riot_api(url, headers, limiter, params=None, timeout=10):
    limiter.acquire()
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code == 429:
        rate_limit_type = response.headers.get("X-Rate-Limit-Type", "service")
        if rate_limit_type in ("application", "method"):
            retry_after = int(response.headers.get("Retry-After", 1))
            time.sleep(retry_after)
            return call_riot_api(url, headers, limiter, params, timeout)  # retry once
        else:
            # service-level: exponential backoff with jitter
            import random
            time.sleep(2 + random.uniform(0, 1))
            return call_riot_api(url, headers, limiter, params, timeout)
    if response.status_code == 404:
        raise RiotApiError(404, url)
    response.raise_for_status()
    return response.json()
```

### Pattern 3: Delta MERGE Deduplication

**What:** All Bronze writes use `MERGE INTO` on the primary key(s) with `WHEN NOT MATCHED THEN
INSERT *`. This is idempotent — re-running the job inserts zero rows for already-ingested data.

**Example:**
```python
# Source: Databricks Delta Lake MERGE documentation
from pyspark.sql import SparkSession
import json

def merge_to_bronze(spark: SparkSession, rows: list[dict], table: str, merge_keys: list[str]):
    df = spark.createDataFrame(rows)
    df.createOrReplaceTempView("_staging")
    key_conditions = " AND ".join(
        f"target.{k} = source.{k}" for k in merge_keys
    )
    spark.sql(f"""
        MERGE INTO {table} AS target
        USING _staging AS source
        ON {key_conditions}
        WHEN NOT MATCHED THEN INSERT *
    """)
```

### Pattern 4: Anti-Join Pre-Check (Avoid Wasting API Quota)

**What:** Before fetching match details, read `bronze.match_ids` and `bronze.match_raw` as
Spark DataFrames, anti-join on `match_id` to get only new IDs, then collect to driver.

**Example:**
```python
# Source: standard Spark anti-join pattern
def get_new_match_ids(spark, region):
    all_ids = spark.sql(
        f"SELECT DISTINCT match_id FROM lol_analytics.bronze.match_ids"
    )
    ingested = spark.sql(
        "SELECT DISTINCT match_id FROM lol_analytics.bronze.match_raw"
    )
    new_ids = all_ids.join(ingested, on="match_id", how="left_anti")
    return [row["match_id"] for row in new_ids.collect()]
```

### Pattern 5: DAB Notebook Task for Ingestion

**What:** Each ingestion module is called from a DAB notebook task. The notebook imports
from `src/` (Git source), instantiates the shared rate limiter once, reads job params via
`dbutils.widgets.get()`, and calls the ingestion function.

**Example:**
```python
# Databricks notebook source
# COMMAND ----------
import sys
sys.path.insert(0, "/Workspace/...")  # NOT needed with source: GIT — Databricks handles path

from src.riot_client import RiotRateLimiter, call_riot_api
from src.config import get_job_params
from src.ingestion.bronze_league_entries import ingest_league_entries

params = get_job_params(dbutils)
limiter = RiotRateLimiter()
api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
ingest_league_entries(spark, limiter, api_key, params["region"], params["tier"])
```

**Note on imports with `source: GIT`:** When DAB runs a notebook with `source: GIT`, the
repo root is available on `sys.path` automatically. Imports of `src.riot_client` work without
`sys.path` manipulation, matching local `pytest` behavior when `src/__init__.py` exists.

### Anti-Patterns to Avoid

- **`time.sleep(0.05)` as the primary throttle:** Naively sleeping 50ms between calls gives
  ~20 req/sec on average but doesn't respect the 2-minute bucket. Use the token bucket.
- **Per-call rate limiter instantiation:** Creating a `RiotRateLimiter()` inside `call_riot_api`
  resets the bucket counters on every call, making the limiter useless. Instantiate once per
  driver process and pass as parameter.
- **`KR` platform on Match-V5 direct calls:** Match-V5 requires regional routing host
  (`asia.api.riotgames.com`), NOT the platform host (`kr.api.riotgames.com`). Using the
  platform host for Match-V5 returns 404.
- **Hardcoding `region` or `tier`:** Both must come from `dbutils.widgets.get()` at runtime.
  The ROADMAP specifies `DEFAULT_MATCH_COUNT = 20` and `KR`/`CHALLENGER` as DAB job parameter
  defaults, not Python constants.
- **DBFS paths or `hive_metastore` references:** UC workspace with `SINGLE_USER` mode — all
  paths must be UC three-part names. Established in Phase 1.
- **Notebooks with `source: WORKSPACE`:** SP file access restrictions in UC workspace break
  WORKSPACE source. Always `source: GIT`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retries | Custom retry loop | `requests` response status checks + explicit `Retry-After` sleep | Riot 429 requires reading the `X-Rate-Limit-Type` header — generic retry libs don't handle this routing logic |
| JSON serialization for Delta writes | Custom serializer | `spark.createDataFrame([{"raw_json": json.dumps(obj), ...}])` | Spark handles row creation from Python dicts natively |
| Token bucket | `ratelimit`, `pyrate_limiter` | Custom `RiotRateLimiter` class | Must simultaneously enforce BOTH buckets; standard libs enforce one bucket |
| Mock HTTP in tests | Live API calls | `pytest-mock` to mock `requests.get` | Already in `requirements-dev.txt`; CI has no Riot API key |
| Spark session in tests | Live cluster | `pyspark` local mode (`SparkSession.builder.master("local")`) | Already in `requirements-dev.txt`; requires Java 11 |

**Key insight:** The dual-bucket requirement is the only genuine custom build. Everything else
uses existing project stack.

---

## Runtime State Inventory

> This phase is greenfield ingestion into empty Bronze tables with no rename/refactor. Skipped.

---

## Common Pitfalls

### Pitfall 1: Platform vs. Regional Routing Host Confusion

**What goes wrong:** Using `kr.api.riotgames.com` (platform host) for Match-V5 calls returns
HTTP 404. Match-V5 requires the regional host (`asia.api.riotgames.com` for KR).

**Why it happens:** Riot has two host namespaces — platform hosts for Summoner-V4 and
League-Exp-V4, regional hosts for Match-V5 and Account-V1.

**How to avoid:** `config.py` provides `get_platform_host()` and `get_region_host()` as
separate functions. Ingestion modules explicitly call the correct function. `ROADMAP.md`
Plan 02-04 documents: "Summoner-V4 uses PLATFORM routing. Account-V1 uses REGIONAL routing."

**Warning signs:** 404s on Match-V5 detail or timeline fetches despite valid match IDs.

### Pitfall 2: Rate Limiter Token Bucket Drift

**What goes wrong:** Under sustained load, the 100 req/2min bucket depletes before 2 minutes
elapses, causing 429s that aren't expected. The pipeline then stalls on backoff.

**Why it happens:** The 2-minute bucket refills at 100/120 = 0.833 tokens/second. If `acquire()`
calls happen in rapid bursts (e.g., after a large batch of match IDs), the per-second bucket
allows them but the 2-minute bucket runs out after ~2 minutes at max throughput.

**How to avoid:** The token bucket pattern naturally handles this — both buckets must have
tokens. The 429 `Retry-After` handler is the safety net when it still happens (e.g., dev key
shared across processes, or clock drift).

**Warning signs:** Pipeline runs fine for first 2 minutes then starts hitting 429s repeatedly.

### Pitfall 3: `dbutils` Not Available in Local Tests

**What goes wrong:** Any test that imports a module calling `dbutils.widgets.get()` at module
level (not inside a function) will fail locally with `NameError: name 'dbutils' is not defined`.

**Why it happens:** `dbutils` is injected by the Databricks runtime, not available in local
pytest.

**How to avoid:** `get_job_params(dbutils)` takes `dbutils` as a parameter — the caller
(notebook) passes it in. The function body never references a global `dbutils`. Tests mock
it as a simple object with `.widgets.get()` mocked.

**Warning signs:** `NameError` on import during `pytest` run before any test executes.

### Pitfall 4: `src/` Not on `sys.path` for pytest

**What goes wrong:** `pytest tests/unit/test_riot_client.py` fails with
`ModuleNotFoundError: No module named 'src'`.

**Why it happens:** pytest's `testpaths = tests/unit` doesn't add the repo root to `sys.path`
automatically without `conftest.py` or `__init__.py` in the right places.

**How to avoid:** Add empty `__init__.py` to `src/`, `src/common/`, and `src/ingestion/`.
pytest with `--cov=src` from the repo root then resolves imports correctly.

**Warning signs:** CI `pytest tests/unit/ --cov=src` passes locally but green on one machine,
red on another due to installed package vs. source tree differences.

### Pitfall 5: `ingestion_job.yml` Replacing Placeholder Breaks `databricks bundle validate`

**What goes wrong:** Replacing `resources/jobs/ingestion_job.yml` with an invalid YAML or
referencing a `job_cluster_key` not defined in the same file causes `bundle validate` to fail,
breaking CI.

**Why it happens:** The DAB job YAML must define `job_clusters` with `job_cluster_key` matching
each task's `job_cluster_key` reference. The smoke test job (`smoke_test_job.yml`) is a safe
reference for the cluster config pattern.

**How to avoid:** Copy the cluster definition from `smoke_test_job.yml` as the base template.
Define `job_cluster_key: main_cluster` once in `job_clusters:` and reference it in all tasks.

**Warning signs:** `databricks bundle validate` exits non-zero with YAML/reference error.

### Pitfall 6: Java Not Installed — `pyspark` Local Mode Silently Fails

**What goes wrong:** `pytest` finds and imports `pyspark`, but any test creating a `SparkSession`
raises `RuntimeError: Java gateway process exited before sending its port number`.

**Why it happens:** Java 11 is not currently installed (`JAVA_HOME` is unset, no JVM found in
`/usr/lib/jvm/`). The `openjdk-11-jdk-headless` package is available in apt but not installed.

**How to avoid:** Install Java before running tests. See Environment Availability section.
Plan 02-05 Wave 0 must include Java installation.

**Warning signs:** Any test using `SparkSession` fails with Java gateway error; tests not
using Spark pass fine.

---

## Code Examples

Verified patterns from ROADMAP.md and established project conventions:

### DAB Job YAML Task Dependency Pattern

```yaml
# Source: ROADMAP.md Plan 02-05, smoke_test_job.yml pattern
resources:
  jobs:
    ingestion_job:
      name: dbx-mls-ingestion
      timeout_seconds: 14400
      parameters:
        - name: region
          default: KR
        - name: tier
          default: CHALLENGER
      git_source:
        git_url: https://github.com/gustavofs-git/dbx-mls
        git_provider: gitHub
        git_branch: main
      job_clusters:
        - job_cluster_key: main_cluster
          new_cluster:
            spark_version: 16.4.x-scala2.12
            node_type_id: Standard_F4s_v2
            num_workers: 0
            data_security_mode: SINGLE_USER
            spark_conf:
              spark.databricks.cluster.profile: singleNode
              spark.master: local[*]
            autotermination_minutes: 0
            custom_tags:
              project: dbx-mls
              job: ingestion
              ResourceClass: SingleNode
      tasks:
        - task_key: league_entries_task
          notebook_task:
            notebook_path: notebooks/ingest_league_entries
            source: GIT
          job_cluster_key: main_cluster
          libraries:
            - pypi:
                package: requests>=2.32.0
        - task_key: match_ids_task
          depends_on:
            - task_key: league_entries_task
          notebook_task:
            notebook_path: notebooks/ingest_match_ids
            source: GIT
          job_cluster_key: main_cluster
          libraries:
            - pypi:
                package: requests>=2.32.0
        # ... (match_raw, match_timeline, summoner, account tasks follow same pattern)
```

### ingestion_log Table Creation (Delta, UC)

```python
# Source: D-06 schema definition; Delta SQL pattern from Phase 1 smoke test
spark.sql("""
    CREATE TABLE IF NOT EXISTS lol_analytics.bronze.ingestion_log (
        batch_id     STRING,
        run_start    TIMESTAMP,
        run_end      TIMESTAMP,
        requests_made    BIGINT,
        count_429    BIGINT,
        new_matches_ingested BIGINT,
        status       STRING
    ) USING DELTA
""")
```

### pytest-mock Pattern for HTTP Mocking

```python
# Source: pytest-mock documentation; standard pattern for requests mocking
def test_normal_response(mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"matchId": "KR_123"}
    mock_response.headers = {"X-App-Rate-Limit-Count": "1:20,1:100"}
    mocker.patch("requests.get", return_value=mock_response)

    limiter = RiotRateLimiter()
    result = call_riot_api("https://test.url", {}, limiter)
    assert result == {"matchId": "KR_123"}

def test_429_application_limit(mocker):
    mock_429 = mocker.Mock()
    mock_429.status_code = 429
    mock_429.headers = {"X-Rate-Limit-Type": "application", "Retry-After": "1"}
    mock_200 = mocker.Mock()
    mock_200.status_code = 200
    mock_200.json.return_value = {}
    mock_200.headers = {}
    mocker.patch("requests.get", side_effect=[mock_429, mock_200])
    mock_sleep = mocker.patch("time.sleep")

    limiter = RiotRateLimiter()
    call_riot_api("https://test.url", {}, limiter)
    mock_sleep.assert_any_call(1)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `time.sleep(1/20)` fixed delay per request | Token bucket with `time.monotonic()` refill | Riot API rate limit enforcement evolution | Handles burst + sustained rate correctly; respects both buckets |
| `hive_metastore` table writes | UC three-part names (`catalog.schema.table`) | Databricks UC GA 2023 | Required for `SINGLE_USER` data security mode |
| `source: WORKSPACE` notebook tasks | `source: GIT` notebook tasks | UC workspace SP restrictions (discovered Phase 1) | SP cannot access WORKSPACE source in UC; GIT source pulls from public GitHub |

**Deprecated/outdated:**
- `time.sleep(0.05)` as primary throttle: explicitly forbidden by ROADMAP (produces uneven
  rate distribution, doesn't honor 2-min bucket)
- `tenacity` for 429 retry: doesn't expose `Retry-After` header value or `X-Rate-Limit-Type`

---

## Open Questions

1. **`src/` import path in Databricks notebook with `source: GIT`**
   - What we know: Phase 1 used `notebooks/smoke_test.py` which imports nothing from `src/`
     (it was empty). With `source: GIT`, the repo root is checked out to a temp path.
   - What's unclear: Whether `import src.riot_client` works without `sys.path` manipulation,
     or whether notebooks need `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`.
   - Recommendation: Test in Wave 0 of Plan 02-03. If import fails, add a single
     `sys.path` prepend to each notebook. The `src/__init__.py` approach should resolve this.

2. **Riot API dev key 24-hour expiry during cold run**
   - What we know: Cold run takes 2-3.5 hours. Dev key expires every 24 hours.
   - What's unclear: Whether key expiry mid-run causes 401 (immediate fail) or 403.
   - Recommendation: The `RiotApiError` typed exception should distinguish 401/403 from
     404. Plan 02-01 should include this in the exception hierarchy. The `ingestion_log`
     `status` field captures failure reason at job level.

3. **`resources/jobs/transformation_job.yml` — does it break `bundle validate` now?**
   - What we know: `transformation_job.yml` exists as a placeholder alongside the ingestion
     placeholder. Both are `jobs: {}`.
   - What's unclear: Whether adding a real `ingestion_job.yml` while `transformation_job.yml`
     remains a placeholder causes any bundle validation conflict.
   - Recommendation: Verify with `databricks bundle validate` after replacing
     `ingestion_job.yml`. The empty `jobs: {}` placeholder has worked in Phase 1 and should
     continue to work.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All src modules, pytest | Yes | 3.12.3 | — |
| `requests` | `src/riot_client.py` | Yes (in requirements.txt) | >=2.32.0 | — |
| `pytest` | TEST-02, TEST-04 | Yes (in requirements-dev.txt) | >=8.3.0 | — |
| `pytest-mock` | Unit tests | Yes (in requirements-dev.txt) | >=3.14.0 | — |
| `pyspark` | Local Delta tests, ingestion modules | Yes (in requirements-dev.txt) | 3.5.3 | — |
| `delta-spark` | Local Delta writes in tests | Yes (in requirements-dev.txt) | 3.3.2 | — |
| Java 11 (JVM) | `pyspark` local mode | NOT INSTALLED | — | `sudo apt install openjdk-11-jdk-headless` |
| Databricks CLI | DAB deploy, `bundle validate` | Yes | v0.295.0 | — |
| `JAVA_HOME` env var | pyspark startup | NOT SET | — | Set after Java install |
| Databricks workspace | UAT / acceptance testing | Yes (Phase 1 verified) | — | — |
| Riot API dev key | UAT only (not unit tests) | Yes (in secret scope) | Dev (24h expiry) | Rotate before long runs |

**Missing dependencies with no fallback:**
- Java 11 + `JAVA_HOME` — blocks all tests that create a `SparkSession` locally. Install
  with: `sudo apt install openjdk-11-jdk-headless` and set
  `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64`. The `openjdk-11-jdk-headless`
  package is available in the apt cache (version 11.0.30 confirmed).

**Missing dependencies with fallback:**
- None — all other dependencies either exist or have the Java install as the sole gap.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.3.0 (already configured) |
| Config file | `pytest.ini` — `testpaths = tests/unit`, `addopts = -v` |
| Quick run command | `pytest tests/unit/test_riot_client.py tests/unit/test_config.py -v` |
| Full suite command | `pytest tests/unit/ --cov=src --cov-report=xml` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRZ-01 | Rate limiter: both buckets decremented per call | unit | `pytest tests/unit/test_riot_client.py::test_buckets_decremented -x` | Wave 0 |
| BRZ-01 | 429 application limit: sleeps `Retry-After` seconds | unit | `pytest tests/unit/test_riot_client.py::test_429_application -x` | Wave 0 |
| BRZ-01 | 429 service limit: exponential backoff | unit | `pytest tests/unit/test_riot_client.py::test_429_service -x` | Wave 0 |
| BRZ-01 | 404: raises `RiotApiError` | unit | `pytest tests/unit/test_riot_client.py::test_404_raises -x` | Wave 0 |
| BRZ-02 | `get_job_params()` reads widgets, defaults to KR/CHALLENGER | unit | `pytest tests/unit/test_config.py::test_get_job_params_defaults -x` | Wave 0 |
| BRZ-03 | All 17 platform-to-region mappings correct | unit | `pytest tests/unit/test_config.py::test_platform_to_region_mapping -x` | Wave 0 |
| BRZ-03 | Unknown platform raises `ConfigError` | unit | `pytest tests/unit/test_config.py::test_unknown_platform_raises -x` | Wave 0 |
| BRZ-04–09 | MERGE dedup: second run produces identical row count | manual | `SELECT COUNT(*) FROM lol_analytics.bronze.match_raw` run twice | N/A (UAT) |
| TEST-04 | pytest runs locally without live cluster | integration | `make test` | depends on Wave 0 Java install |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_riot_client.py tests/unit/test_config.py -v`
- **Per wave merge:** `pytest tests/unit/ --cov=src --cov-report=xml`
- **Phase gate:** Full suite green + UAT acceptance test (real job run) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_riot_client.py` — covers BRZ-01 rate limiter and 429 handling
- [ ] `tests/unit/test_config.py` — covers BRZ-02, BRZ-03
- [ ] `src/__init__.py` — empty file enabling `import src.riot_client` in tests
- [ ] `src/common/__init__.py` — empty
- [ ] `src/ingestion/__init__.py` — empty
- [ ] Java 11 install: `sudo apt install openjdk-11-jdk-headless` + `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64`

---

## Sources

### Primary (HIGH confidence)

- `ROADMAP.md` §Phase 2, Plans 02-01 through 02-05 — exact deliverables, class names, method
  signatures, table schemas, acceptance criteria, task DAG
- `02-CONTEXT.md` — locked implementation decisions D-01 through D-06
- `requirements.txt` + `requirements-dev.txt` — confirmed installed packages and versions
- `resources/jobs/smoke_test_job.yml` — authoritative DAB cluster config pattern (DBR 16.4 LTS,
  `SINGLE_USER`, `Standard_F4s_v2`, `source: GIT`)
- `pytest.ini` + `ci.yml` — confirmed test runner config and CI command
- `schema_report.md` — Riot API field schemas from real API responses
- `STATE.md` §Accumulated Context — Phase 1 constraints: `SINGLE_USER`, `source: GIT`,
  `DATABRICKS_HOST` via env var

### Secondary (MEDIUM confidence)

- Riot Games Developer Portal API docs — routing host separation (platform vs. regional),
  429 header fields (`X-Rate-Limit-Type`, `Retry-After`, `X-App-Rate-Limit-Count`)
  — ROADMAP.md captures this fully, no direct web verification performed

### Tertiary (LOW confidence)

- Token bucket algorithm: standard CS algorithm, widely documented — no single authoritative
  source; implementation in `riot_client.py` follows canonical pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified in `requirements.txt` / `requirements-dev.txt`
- Architecture: HIGH — ROADMAP.md defines exact file paths, class names, schemas; no guesswork
- Pitfalls: HIGH for routing/import/Java gaps (verified from existing code); MEDIUM for token
  bucket drift (standard algorithm behavior, not tested against live Riot API)
- Environment: HIGH — directly probed with shell commands

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable stack; Riot API routing conventions change rarely)
