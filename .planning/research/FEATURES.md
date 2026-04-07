# Feature Landscape: Riot Games API Ingestion into Databricks Medallion Architecture

**Domain:** Batch API ingestion pipeline — Riot Games LoL endpoints to Databricks Bronze layer
**Researched:** 2026-04-07
**Confidence:** HIGH (rate limits, routing confirmed from official Riot Developer Portal; Databricks patterns from official docs)

---

## Table Stakes

Features the pipeline must have to function correctly. Missing any of these = broken pipeline.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Rate limit enforcement | Dev key: 20 req/sec, 100 req/2min hard caps — violating causes progressive blacklisting | Medium | Token bucket + Retry-After header parsing required |
| Match routing vs platform separation | KR platform must query `asia` regional host — wrong host returns 404/empty | Low | One lookup table, zero ambiguity once documented |
| Two-step player seeding (tier → PUUID → matches) | No direct match endpoint by tier — must traverse the hierarchy | Medium | Sequential dependency: League-Exp-V4 → Match-V5/by-puuid → Match-V5/detail |
| Incremental match deduplication | Re-running pipeline must not double-insert already-ingested matches | Medium | MERGE on `match_id` or set-difference pre-check |
| Bronze raw JSON preservation | Silver transformations may change; Bronze must allow replay from source-faithful data | Low | Store as STRING column, never parse at Bronze |
| Ingestion metadata columns | `_ingested_at`, `_source_url`, `_region`, `_tier` required for lineage and incremental logic | Low | Add at write time, not fetched from API |
| Secrets via Databricks Secrets | API key must never appear in code, notebooks, or DAB YAML | Low | `dbutils.secrets.get(scope, key)` pattern |
| Parameterized region and tier | No code changes to switch KR/Challenger to NA1/Diamond | Low | DAB job parameters, read via `dbutils.widgets` |

---

## Detailed Feature Specifications

### Feature 1: Rate Limit Enforcement

**Dev key limits (confirmed from Riot Developer Portal):**
- Application limit 1: 20 requests per 1 second
- Application limit 2: 100 requests per 2 minutes (120 seconds)
- Method limits: exist per-endpoint but not publicly documented — parse from response headers

**The two-bucket problem.** The 2-minute bucket is the real constraint. At 100 req/2min, the sustained throughput ceiling is 0.83 requests/second, far below the 20 req/sec burst limit. Any loop that ignores the 2-minute bucket will hit it within seconds.

**Rate limiting implementation — prescriptive approach:**

Do NOT use a naive `time.sleep(0.05)` between requests. This only addresses the per-second bucket and will blow the 2-minute bucket.

Use a **dual-bucket token bucket** implementation:

```python
import time
import threading

class RiotRateLimiter:
    """
    Enforces both Riot Dev key buckets:
      - 20 requests / 1 second
      - 100 requests / 2 minutes (120 seconds)
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._short_tokens = 20      # per-second bucket capacity
        self._long_tokens = 100      # 2-minute bucket capacity
        self._short_refill_time = 1.0
        self._long_refill_time = 120.0
        self._short_last_refill = time.monotonic()
        self._long_last_refill = time.monotonic()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            # Refill short bucket
            short_elapsed = now - self._short_last_refill
            if short_elapsed >= self._short_refill_time:
                self._short_tokens = 20
                self._short_last_refill = now
            # Refill long bucket
            long_elapsed = now - self._long_last_refill
            if long_elapsed >= self._long_refill_time:
                self._long_tokens = 100
                self._long_last_refill = now
            # Block until both buckets have capacity
            while self._short_tokens < 1 or self._long_tokens < 1:
                self._lock.release()
                time.sleep(0.05)
                self._lock.acquire()
                now = time.monotonic()
                if now - self._short_last_refill >= self._short_refill_time:
                    self._short_tokens = 20
                    self._short_last_refill = now
                if now - self._long_last_refill >= self._long_refill_time:
                    self._long_tokens = 100
                    self._long_last_refill = now
            self._short_tokens -= 1
            self._long_tokens -= 1
```

**Retry on 429 — honor the Retry-After header:**

When 429 is returned, the `X-Rate-Limit-Type` header tells you whether it was `application`, `method`, or `service`:
- `application` or `method`: `Retry-After` header is present. Sleep exactly that many seconds, then retry.
- `service`: No `Retry-After`. Use exponential backoff with jitter.

```python
import requests
import time
import random
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

def call_riot_api(url: str, headers: dict, limiter: RiotRateLimiter) -> dict:
    limiter.acquire()
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 5))
        limit_type = resp.headers.get("X-Rate-Limit-Type", "service")
        if limit_type in ("application", "method"):
            time.sleep(retry_after)
        else:
            # Service limit — exponential backoff with jitter
            time.sleep(retry_after + random.uniform(0, 2))
        return call_riot_api(url, headers, limiter)  # retry once
    resp.raise_for_status()
    return resp.json()
```

**Never hardcode limit values.** Parse `X-App-Rate-Limit` and `X-Method-Rate-Limit` from response headers to detect if Riot changes limits without notice. Log these values on first call.

**Recommended HTTP client: `requests` (synchronous) over `httpx` (async).**
Databricks notebooks run inside Jupyter-like environments with an active event loop. `asyncio` in Databricks requires `nest_asyncio` workarounds that add fragility. Since the rate limiter itself must serialize requests to stay within the 2-minute bucket, async concurrency provides minimal benefit. Use `requests` with the dual-bucket limiter above. If parallelism is needed later (separate worker threads per tier), use Python `threading` with the thread-safe limiter above.

---

### Feature 2: Match Routing vs Platform (Critical Gotcha)

**Platform routing values** — used for Summoner-V4, League-Exp-V4, League-V4:
- Format: `{platform}.api.riotgames.com` (e.g., `kr.api.riotgames.com`)

**Regional routing values** — required for Account-V1 and ALL Match-V5 endpoints:
- Format: `{region}.api.riotgames.com` (e.g., `asia.api.riotgames.com`)

**Complete mapping (HIGH confidence — verified from Riot Developer Portal):**

| Platform | Region Host | Example Endpoint |
|----------|-------------|-----------------|
| KR | `asia` | `asia.api.riotgames.com` |
| JP1 | `asia` | `asia.api.riotgames.com` |
| NA1 | `americas` | `americas.api.riotgames.com` |
| BR1 | `americas` | `americas.api.riotgames.com` |
| LA1 | `americas` | `americas.api.riotgames.com` |
| LA2 | `americas` | `americas.api.riotgames.com` |
| EUW1 | `europe` | `europe.api.riotgames.com` |
| EUN1 | `europe` | `europe.api.riotgames.com` |
| TR1 | `europe` | `europe.api.riotgames.com` |
| RU | `europe` | `europe.api.riotgames.com` |
| ME1 | `europe` | `europe.api.riotgames.com` |
| OC1 | `sea` | `sea.api.riotgames.com` |
| PH2 | `sea` | `sea.api.riotgames.com` |
| SG2 | `sea` | `sea.api.riotgames.com` |
| TH2 | `sea` | `sea.api.riotgames.com` |
| TW2 | `sea` | `sea.api.riotgames.com` |
| VN2 | `sea` | `sea.api.riotgames.com` |

**For this project (KR platform):**
- League-Exp-V4: `https://kr.api.riotgames.com/lol/league-exp/v4/entries/RANKED_SOLO_5x5/{tier}/I`
- Summoner-V4: `https://kr.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}`
- Match-V5 IDs: `https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids`
- Match-V5 Detail: `https://asia.api.riotgames.com/lol/match/v5/matches/{matchId}`
- Match-V5 Timeline: `https://asia.api.riotgames.com/lol/match/v5/matches/{matchId}/timeline`
- Account-V1: `https://asia.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}`

Encode this as a lookup dictionary keyed by platform in a `config.py`, not scattered across notebooks.

---

### Feature 3: Two-Step Seeding Flow (League-Exp-V4 → PUUIDs → Matches)

**The full pipeline dependency chain:**

```
Step 1: League-Exp-V4
  GET /lol/league-exp/v4/entries/RANKED_SOLO_5x5/{TIER}/I?page={n}
  → Returns: list[LeagueEntryDTO]  (contains puuid field)
  → ~200 entries/page for most tiers
  → Challenger KR: ~300 entries total (1-2 pages)
  → Grandmaster KR: ~700 entries total (3-4 pages)
  → Stop condition: empty list returned

Step 2: Match-V5 IDs (per PUUID)
  GET /lol/match/v5/matches/by-puuid/{puuid}/ids
    ?queue=420        (RANKED_SOLO_5x5 only)
    &start=0
    &count=20         (fetch last 20 matches per player, sufficient for recent meta)
  → Returns: list[string] match IDs

Step 3: Match-V5 Detail (per match ID)
  GET /lol/match/v5/matches/{matchId}
  → Returns: MatchDTO (metadata + info with participants array)

Step 4: Match-V5 Timeline (per match ID, optional, expensive)
  GET /lol/match/v5/matches/{matchId}/timeline
  → Returns: MatchTimelineDto (frames array, ~28 frames per match)
```

**Volume estimate for KR Challenger + Grandmaster (schema_report.md confirms ~200 entries/page):**
- Players: ~1,000 total (Challenger ~300 + Grandmaster ~700)
- Match IDs fetched: ~20,000 (20 per player)
- Unique matches after dedup: ~5,000-8,000 (10 players share each match)
- Match detail API calls: ~5,000-8,000
- Timeline API calls: same count (if ingested)
- Total API calls: ~6,000-10,000 per full run
- Time at 100 req/2min sustained rate: ~2-3.5 hours for a cold run

This estimate is important for DAB job timeout configuration.

---

### Feature 4: League-Exp-V4 Pagination

**Pagination parameter:** `?page=1` (1-indexed, not 0-indexed)

**Stop condition:** API returns an empty list `[]` — this is the only reliable termination signal. There is no `total_pages` or `X-Total-Count` header.

**Known hard cap:** For lower tiers (Iron through Diamond), the API caps results at approximately 10,000 entries (49 pages × ~205 entries). The pipeline must handle this gracefully — do not treat the cap as an error. For Challenger and Grandmaster in KR, the total entries are small (< 1,000) and this cap does not apply.

**Apex tier behavior:** Challenger and Grandmaster do not use division (`/I`, `/II`, etc.) — they exist as a single division `I` only. The endpoint still uses `/I` in the URL path for these tiers.

**Correct pagination loop:**

```python
def fetch_all_league_entries(platform: str, tier: str, queue: str, headers: dict, limiter) -> list:
    entries = []
    page = 1
    while True:
        url = f"https://{platform}.api.riotgames.com/lol/league-exp/v4/entries/{queue}/{tier}/I"
        data = call_riot_api(url, headers=headers, limiter=limiter, params={"page": page})
        if not data:  # empty list = no more pages
            break
        entries.extend(data)
        page += 1
    return entries
```

---

### Feature 5: Incremental Loading Strategy — Match Deduplication

**Problem:** Challenger players share matches. 10 players = 1 match. If you fetch 20 matches for 1,000 players, you get 20,000 match IDs but only ~5,000-8,000 unique matches. Re-running the pipeline generates the same match IDs again.

**Recommended strategy: Insert-only MERGE on `match_id` (deduplication via WHEN NOT MATCHED)**

This is the Delta Lake standard pattern for idempotent append-only tables:

```sql
MERGE INTO lol_analytics.bronze.match_raw AS target
USING (SELECT * FROM new_matches_stage) AS source
ON target.match_id = source.match_id
WHEN NOT MATCHED THEN INSERT *
```

**Do NOT use `overwrite` mode on the Bronze table.** Bronze is the source of truth. Overwrites destroy the ability to replay from raw.

**Pre-check optimization (recommended for large runs):** Before calling the Match-V5 API for each match ID, check whether it already exists in `bronze.match_raw`. This avoids wasting API quota fetching data you already have.

```python
def get_new_match_ids(spark, all_match_ids: list[str]) -> list[str]:
    """Return only match IDs not already in bronze.match_raw."""
    existing = spark.table("lol_analytics.bronze.match_raw") \
                    .select("match_id") \
                    .rdd.flatMap(lambda x: x).collect()
    existing_set = set(existing)
    return [mid for mid in all_match_ids if mid not in existing_set]
```

For large tables, use a Spark join instead of `.collect()`:

```python
new_ids_df = spark.createDataFrame([(mid,) for mid in all_match_ids], ["match_id"])
existing_df = spark.table("lol_analytics.bronze.match_raw").select("match_id")
new_only_df = new_ids_df.join(existing_df, on="match_id", how="left_anti")
return [row.match_id for row in new_only_df.collect()]
```

**Watermark approach (alternative, not recommended for this pipeline):** A time-based watermark using `gameEndTimestamp` is tempting but fragile — matches can appear in the API days after they were played. The set-difference approach on `match_id` is more reliable.

---

### Feature 6: Bronze Table Schema Design

**Design principle:** Bronze stores the API response as-is. The Silver layer is responsible for interpretation. Bronze schemas must never block replay.

#### `bronze.league_entries`

```sql
CREATE TABLE lol_analytics.bronze.league_entries (
  raw_json        STRING NOT NULL,     -- full JSON of one LeagueEntryDTO as string
  puuid           STRING NOT NULL,     -- extracted for lookup, redundant with raw_json
  tier            STRING NOT NULL,     -- runtime parameter (e.g., 'CHALLENGER')
  queue_type      STRING NOT NULL,     -- always 'RANKED_SOLO_5x5' for this project
  _region         STRING NOT NULL,     -- platform code (e.g., 'KR')
  _page           INT    NOT NULL,     -- source page number for debugging
  _ingested_at    TIMESTAMP NOT NULL,  -- current_timestamp() at write time
  _source_url     STRING               -- full URL called (without API key)
)
USING DELTA
PARTITIONED BY (_region, tier)
COMMENT 'Bronze: raw LeagueEntryDTO records from League-Exp-V4. One row per player per ingestion run.';
```

#### `bronze.match_ids`

```sql
CREATE TABLE lol_analytics.bronze.match_ids (
  puuid           STRING NOT NULL,
  match_id        STRING NOT NULL,
  _region         STRING NOT NULL,
  _tier           STRING NOT NULL,
  _ingested_at    TIMESTAMP NOT NULL,
  _source_url     STRING
)
USING DELTA
PARTITIONED BY (_region, _tier)
COMMENT 'Bronze: match ID lists from Match-V5 by-puuid. One row per (puuid, match_id) pair.';
```

#### `bronze.match_raw`

```sql
CREATE TABLE lol_analytics.bronze.match_raw (
  match_id        STRING NOT NULL,     -- extracted from metadata.matchId
  raw_json        STRING NOT NULL,     -- full MatchDTO JSON as string
  platform_id     STRING NOT NULL,     -- e.g., 'KR' (from info.platformId)
  game_creation   BIGINT,              -- epoch ms (from info.gameCreation) — for partitioning
  _region         STRING NOT NULL,     -- routing region used (e.g., 'asia')
  _tier           STRING NOT NULL,     -- tier that seeded this match
  _ingested_at    TIMESTAMP NOT NULL,
  _source_url     STRING
)
USING DELTA
PARTITIONED BY (_region, _tier)
COMMENT 'Bronze: full MatchDTO JSON from Match-V5 detail. One row per unique match_id. Deduplicated via MERGE.';
```

**Partitioning note:** Partition by `(_region, _tier)` rather than date. For this pipeline (KR only, Challenger + Grandmaster), date partitioning creates many small partitions with little benefit. Region + tier partitions align with how the Silver layer reads (always by region and tier). Consider Liquid Clustering (available on DBR 13.3+) as an alternative to static partitioning for better query adaptability.

#### `bronze.match_timeline_raw`

```sql
CREATE TABLE lol_analytics.bronze.match_timeline_raw (
  match_id        STRING NOT NULL,
  raw_json        STRING NOT NULL,     -- full MatchTimelineDto JSON as string
  _region         STRING NOT NULL,
  _tier           STRING NOT NULL,
  _ingested_at    TIMESTAMP NOT NULL,
  _source_url     STRING
)
USING DELTA
PARTITIONED BY (_region, _tier)
COMMENT 'Bronze: full MatchTimelineDto JSON from Match-V5 timeline. One row per match_id.';
```

**Timeline volume warning:** Each timeline JSON is large (~28 frames × 10 participants × 47 fields = ~13,160 cells per match). For 6,000 matches, this is significant storage. Ingest timeline in a separate job step, not inline with match detail ingestion, so match detail can succeed independently.

#### `bronze.summoner_raw`

```sql
CREATE TABLE lol_analytics.bronze.summoner_raw (
  puuid           STRING NOT NULL,
  raw_json        STRING NOT NULL,
  _region         STRING NOT NULL,
  _tier           STRING NOT NULL,
  _ingested_at    TIMESTAMP NOT NULL,
  _source_url     STRING
)
USING DELTA
PARTITIONED BY (_region, _tier)
COMMENT 'Bronze: Summoner-V4 profiles. One row per puuid per ingestion run.';
```

#### `bronze.account_raw`

```sql
CREATE TABLE lol_analytics.bronze.account_raw (
  puuid           STRING NOT NULL,
  raw_json        STRING NOT NULL,
  _region         STRING NOT NULL,
  _ingested_at    TIMESTAMP NOT NULL,
  _source_url     STRING
)
USING DELTA
PARTITIONED BY (_region)
COMMENT 'Bronze: Account-V1 account details. One row per puuid per ingestion run.';
```

**Why STRING for raw_json, not MAP or STRUCT?**
1. Riot adds fields without notice. A STRUCT schema enforced at Bronze will fail on new fields.
2. STRING allows exact replay: `from_json(raw_json, inferred_schema)` at Silver time with the schema you choose.
3. Unity Catalog schema evolution for STRUCT columns requires explicit `MERGE SCHEMA` — fragile for a rapidly-changing API.
4. Silver parsers can use `schema_of_json` or explicit DDL schemas. Bronze never should.

---

### Feature 7: Participant Object Handling (147 Fields)

The participant object (schema_report.md section 6) has three embedded complex objects that require special attention at Bronze time — but Bronze ignores them completely (raw JSON string). Silver is responsible for:

- `challenges` (125 fields): Explode as a flat struct or separate table. Recommended: separate `silver.match_participant_challenges` table — 125 columns in the main participants table creates query usability problems.
- `perks` (2 top-level fields → `statPerks` + `selections`): Flatten `statPerks` inline; `selections` (rune selections array) → separate `silver.match_participant_perks` table.
- `missions` (12 fields): Flatten inline into `silver.match_participants` — only 12 fields, no nesting.
- `PlayerBehavior` (1 field): Flatten inline.

This is a Silver-layer concern, but Bronze schema design must account for it: raw_json must be the full participant JSON including these nested objects, not a partial extraction.

---

## Differentiators

Features that make this portfolio project stand out beyond basic functionality.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Header-driven rate limit logging | Parse `X-App-Rate-Limit-Count` headers and emit metrics — demonstrates production instrumentation | Low | Log as structured JSON to a Delta table or stdout |
| Idempotent job design | Re-running any job step produces the same result — shows understanding of pipeline reliability | Medium | MERGE at Bronze, no side effects |
| DAB-parameterized routing | Single codebase handles any Riot region by changing a job parameter — shows infrastructure maturity | Low | One `PLATFORM_TO_REGION` dict in config |
| Separate timeline ingestion task | Timeline is optional and expensive — isolating it as a separate DAB task shows architectural judgment | Low | Two tasks in one job: `ingest_matches` and `ingest_timelines` |
| Rate limit metrics table | Write a small `bronze.ingestion_log` row per job run with requests_made, 429_count, duration_seconds | Low | Demonstrates operational observability |

---

## Anti-Features

Patterns to explicitly avoid.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Parsing JSON at Bronze write time | Breaks on new API fields; locks in a schema Riot can invalidate | Store raw STRING, parse at Silver |
| `time.sleep(0.05)` naive throttling | Ignores 2-minute bucket; will hit 429 within seconds | Dual-bucket token bucket with Retry-After header |
| Using platform routing for Match-V5 | `kr.api.riotgames.com/lol/match/v5/...` returns 404 | Always use `asia.api.riotgames.com` for KR match data |
| Overwrite mode on Bronze tables | Destroys ingestion history; cannot replay to Silver | Insert-only with MERGE deduplication |
| Fetching all match history per player | Match-V5 by-puuid has a ~990 match practical limit; fetching 100s wastes quota | Use `count=20` for recent matches; `start=0` |
| Inline timeline ingestion | Timeline JSON is large and adds latency; failure blocks match detail writes | Separate DAB task, separate Bronze table |
| Hardcoding "KR" or "asia" as constants | Defeats parameterization requirement | Runtime DAB parameters, config lookup dict |
| Using `hive_metastore` for any table | Project constraint: Unity Catalog only | Three-part names: `lol_analytics.{layer}.{table}` |
| asyncio in Databricks notebooks | Requires `nest_asyncio` workarounds; adds fragility for no throughput gain | Synchronous `requests` + thread-safe rate limiter |

---

## Feature Dependencies

```
League-Exp-V4 fetch (Step 1)
  → produces: puuid list
  → writes to: bronze.league_entries

PUUID list → Match-V5 ID fetch (Step 2)
  → produces: match_id list
  → writes to: bronze.match_ids
  → requires: puuid list from Step 1

match_id list + bronze.match_raw dedup check
  → produces: new_match_ids (set difference)
  → no write

new_match_ids → Match-V5 detail fetch (Step 3)
  → writes to: bronze.match_raw
  → requires: new_match_ids

new_match_ids → Match-V5 timeline fetch (Step 4, separate task)
  → writes to: bronze.match_timeline_raw
  → requires: new_match_ids (can run in parallel with Step 3 or after)

puuid list → Summoner-V4 fetch (Step 5, optional)
  → writes to: bronze.summoner_raw
  → requires: puuid list from Step 1

puuid list → Account-V1 fetch (Step 6, optional)
  → writes to: bronze.account_raw
  → requires: puuid list from Step 1
  → uses: asia routing (not kr platform routing)
```

---

## MVP Recommendation

**Prioritize for Phase 1 (Bronze ingestion):**
1. League-Exp-V4 full pagination → `bronze.league_entries`
2. Match-V5 IDs (count=20 per PUUID) → `bronze.match_ids`
3. Match-V5 detail with deduplication MERGE → `bronze.match_raw`
4. Dual-bucket rate limiter with Retry-After handling

**Defer to Phase 1b or Phase 2:**
- Match-V5 timeline (separate task, high volume)
- Summoner-V4 and Account-V1 (enrichment, not required for match analytics)

**Defer to Gold layer design phase:**
- Any aggregation or incremental update logic beyond simple dedup

---

## Sources

- Riot Developer Portal — Dev key rate limits (20 req/sec, 100 req/2min): https://developer.riotgames.com/docs/portal
- Riot API routing documentation: https://darkintaqt.com/blog/routing
- Hextechdocs — Rate limiting headers and 429 handling: https://hextechdocs.dev/rate-limiting/
- Riot API libraries community docs (pagination stop condition): https://riot-api-libraries.readthedocs.io/
- GitHub/RiotGames developer-relations issue #1115 (10,000 entry cap on league-exp-v4): https://github.com/RiotGames/developer-relations/issues/1115
- GitHub/RiotGames developer-relations issue #517 (match history ~990 limit): https://github.com/RiotGames/developer-relations/issues/517
- Databricks Delta Lake MERGE documentation: https://learn.microsoft.com/en-us/azure/databricks/delta/merge
- Tenacity Python library: https://tenacity.readthedocs.io/
- HTTPX vs requests comparison: https://www.proxy-cheap.com/blog/httpx-vs-requests
- Databricks async community discussion: https://community.databricks.com/t5/data-engineering/asynchronous-api-calls-from-databricks/td-p/4691
