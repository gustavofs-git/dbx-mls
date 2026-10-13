# Code architecture

## Package layout

```
src/mls/
├── common/
│   ├── logger.py            # Logger — structured stdout, readable in the Databricks task log
│   ├── run_context.py       # RunContext — run_id, job name, target, scope configuration
│   ├── pseudonymize.py      # puuid -> player_sk, HMAC-SHA256 with a salt from the secret scope
│   └── spark_io.py          # read/write helpers, audit column injection
├── riot/
│   ├── auth.py              # TokenManager — reads the secret scope, probes the key, reports validity
│   ├── client.py            # RiotClient — rate limiting, retry with backoff, routing
│   └── endpoints.py         # endpoint descriptors: path, routing kind, rate cost
├── ingest/
│   ├── base.py              # BaseIngestor — template method: plan -> fetch -> land -> report
│   ├── league_v4.py         # LeagueV4Ingestor
│   └── match_v5.py          # MatchV5Ingestor, MatchV5TimelineIngestor
├── transforms/
│   ├── base.py              # BaseBronzeToHarmonized — template method
│   ├── extract.py           # the only module that touches VARIANT syntax
│   ├── matches.py           # MatchesTransform, MatchParticipantsTransform, MatchTeamsTransform
│   ├── timelines.py         # ParticipantFramesTransform, TimelineEventsTransform
│   ├── league.py            # LeagueEntriesTransform
│   └── registry.py          # ordered lists the pipeline files iterate over
└── quality/
    └── metrics.py           # DQ measurement writers for ops.dq_metrics

pipelines/
├── bronze.py                # one file; iterates BRONZE_SOURCES
├── harmonized.py            # one file; iterates HARMONIZED_TRANSFORMS
└── consumption.py           # one file; view DDL

conf/
├── ingestion_scope.yml      # regions, tiers, sample sizes — configuration, not code
└── dim_queue.csv            # static seed

tests/
├── transforms/              # pure function tests, no Databricks required
├── riot/                    # client tests against recorded fixtures
├── common/                  # pseudonymization stability, logger redaction
└── fixtures/                # recorded Riot API responses
```

## Two patterns, applied deliberately

### Template method for the skeleton

Every bronze → harmonized transform does the same seven things. Only one of them differs per
entity. The base class writes the six shared steps once and leaves exactly one abstract hole.

```python
# src/mls/transforms/base.py
class BaseBronzeToHarmonized(ABC):
    source_table: str
    target_table: str
    natural_key: tuple[str, ...]
    expectations: dict[str, str]

    def __init__(self, spark, logger, run_ctx):
        self.spark = spark
        self.logger = logger
        self.run_ctx = run_ctx

    def run(self) -> DataFrame:
        """Written once. Subclasses never override this."""
        self.logger.start(self.target_table)
        source = self.read()
        out = self.transform(source)          # <- the only hole
        out = self.deduplicate(out)
        out = self.add_audit_columns(out)
        self.logger.finish(self.target_table)
        return out

    def read(self) -> DataFrame:
        return self.spark.read.table(self.qualified(self.source_table))

    def deduplicate(self, df: DataFrame) -> DataFrame:
        window = Window.partitionBy(*self.natural_key).orderBy(col("meta_ingested_at").desc())
        return df.withColumn("_rn", row_number().over(window)).filter("_rn = 1").drop("_rn")

    def add_audit_columns(self, df: DataFrame) -> DataFrame:
        return (df
                .withColumn("meta_pipeline_run_id", lit(self.run_ctx.run_id))
                .withColumn("meta_processed_at", current_timestamp()))

    @abstractmethod
    def transform(self, df: DataFrame) -> DataFrame:
        """Entity-specific flattening. Pure: DataFrame in, DataFrame out."""
```

```python
# src/mls/transforms/matches.py
class MatchParticipantsTransform(BaseBronzeToHarmonized):
    source_table = "bronze.riot_matches"
    target_table = "harmonized.match_participants"
    natural_key  = ("match_id", "participant_id")
    expectations = {
        "valid_champion":  "champion_name IS NOT NULL",
        "sane_kills":      "kills >= 0",
        "sane_deaths":     "deaths >= 0",
        "sane_assists":    "assists >= 0",
        "valid_team":      "team_id IN (100, 200)",
    }

    def transform(self, df: DataFrame) -> DataFrame:
        return explode_participants(df)   # from transforms/extract.py
```

Adding an entity is one class and one method. Logging, deduplication, audit columns and
qualification come for free, and a fix to the skeleton fixes every entity at once.

### Composition for collaborators

`Logger`, `RiotClient` and `RunContext` are injected, never inherited.

```python
class MatchV5Ingestor(BaseIngestor):        # IS A ingestor          -> inheritance
    def __init__(self, client, logger, run_ctx):
        self.client = client                 # HAS A client          -> composition
        self.logger = logger                 # HAS A logger          -> composition
```

The practical reason is testability: a test injects a fake client that replays recorded
fixtures and a fake logger that records calls. If `Logger` were a base class, neither could
be substituted. "Is a" vs "has a" is the whole rule.

## How class-based code lives inside a declarative pipeline

Declarative pipeline files are **generated from a registry**, so there is one pipeline file
per layer, not one per entity.

```python
# pipelines/harmonized.py
import dlt
from mls.common.logger import Logger
from mls.common.run_context import RunContext
from mls.transforms.registry import HARMONIZED_TRANSFORMS

logger, run_ctx = Logger(), RunContext.from_pipeline()

for transform_cls in HARMONIZED_TRANSFORMS:
    def _register(cls=transform_cls):
        instance = cls(spark, logger, run_ctx)

        @dlt.table(name=cls.target_table.split(".")[-1], comment=cls.__doc__)
        @dlt.expect_all_or_drop(cls.expectations)
        def _table():
            return instance.run()

    _register()
```

Two details that matter:

**`cls=transform_cls` as a default argument.** Without it, every closure would capture the
last value of the loop variable and all tables would be built from the same transform. This
is the classic late-binding bug in Python loops, and in a pipeline it fails silently with
wrong data rather than loudly with an exception.

**`@dlt.expect_all_or_drop` reads the expectations off the class.** Quality rules live next to
the transform that produces the columns they check, not in a separate configuration file that
drifts out of sync.

## Testability and the VARIANT boundary

`dlt` only exists inside the pipeline runtime, so any logic inside a decorated function is
untestable. All logic therefore lives in `transform()` methods and in `transforms/extract.py`,
which are plain functions over DataFrames.

One open risk: `VARIANT` is a Databricks Runtime type and may not exist in open-source
PySpark, which is what runs in GitHub Actions. If confirmed, the mitigation is already in the
layout — **`transforms/extract.py` is the only module that writes `VARIANT` navigation
syntax**. Every other transform receives an already-extracted DataFrame and is therefore
testable on vanilla PySpark. `extract.py` is then covered by integration tests in the
workspace rather than unit tests in CI.

This is tracked in the [validation plan](../operations/validation-plan.md).

## Configuration over code

Ingestion scope is data, not logic:

```yaml
# conf/ingestion_scope.yml
platforms:
  - platform_id: kr
    region: asia
    queues: [RANKED_SOLO_5x5]
    tiers:
      - tier: CHALLENGER
        divisions: [I]
        max_players: 300
        matches_per_player: 3
        include_timeline: true
```

The `dev` bundle target overrides `max_players: 5` and `matches_per_player: 1`. Changing
analytical scope — adding Grandmaster, adding a second region — is a reviewed change to one
YAML file, with no code modification and a visible diff in the pull request.

## Error handling in the client

```python
class RiotClient:
    """Token-bucket rate limiting, exponential backoff, and routing awareness."""

    def get(self, endpoint, **params):
        for attempt in range(self.max_retries):
            self._bucket.acquire()                      # blocks until a token is available
            response = self._session.get(...)

            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:             # rate limited
                self._sleep(self._retry_after(response, attempt))
                continue
            if response.status_code in (401, 403):      # key invalid or expired
                raise CredentialError(response.status_code)
            if response.status_code in (500, 502, 503, 504):
                self._sleep(self._backoff(attempt))
                continue
            if response.status_code == 404:             # legitimately absent
                return None
            raise RiotApiError(response.status_code, endpoint)
        raise RetriesExhausted(endpoint)
```

`CredentialError` is caught at the job level and converted into a recorded skip rather than a
failure — see the [resilience model](overview.md#resilience-model). Every other exhaustion
path fails loudly, because silently ingesting a partial ladder is worse than ingesting
nothing.
