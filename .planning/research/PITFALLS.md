# Domain Pitfalls: Databricks Asset Bundles CI/CD with GitHub Actions on Azure

**Domain:** Databricks Asset Bundles (DABs) CI/CD, Unity Catalog, Azure Databricks
**Researched:** 2026-04-07
**Confidence:** HIGH (all critical claims verified against official Microsoft Learn / Databricks docs)

---

## Critical Pitfalls

Mistakes that cause silent failures, pipeline breakage, or require rewrites.

---

### Pitfall 1: Using PAT Tokens Instead of OIDC for GitHub Actions Authentication

**What goes wrong:** Developers reach for Personal Access Tokens (PATs) or manually-generated OAuth SP tokens because they are familiar and the docs show them first. PATs are tied to a human user identity, expire, and must be rotated manually. When the token expires or the user leaves, every pipeline silently breaks.

**Why it happens:** The Microsoft Learn GitHub Actions page shows two patterns side by side — OIDC (the new way) and `SP_TOKEN` (the legacy way). The `SP_TOKEN` example is simpler and requires fewer setup steps, so first-timers use it.

**Consequences:** Expired tokens cause midnight pipeline failures. The token is stored as a long-lived GitHub secret, which is a credential that can be exfiltrated. Rotating it requires manual intervention.

**Prevention — the correct OIDC setup for Azure Databricks:**

Step 1: Create a service principal in the Databricks account console (not Azure AD — the Databricks account-level SP). Note the SP's numeric ID (not the app ID UUID — the numeric ID from the account console).

Step 2: Create a federation policy scoped to your specific GitHub repo and environment:

```bash
databricks account service-principal-federation-policy create <SP_NUMERIC_ID> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["<YOUR_DATABRICKS_ACCOUNT_ID>"],
    "subject": "repo:<github-org>/<repo-name>:environment:prod"
  }
}'
```

Step 3: Add the SP to your workspace with appropriate permissions (see Pitfall 4 for required UC grants).

Step 4: Set two repository variables in GitHub (not secrets — these are not sensitive):
- `DATABRICKS_HOST`: your workspace URL, e.g. `https://adb-<id>.azuredatabricks.net`
- `DATABRICKS_CLIENT_ID`: the SP application (client) UUID

Step 5: In the GitHub Actions workflow, add `id-token: write` permission and set `DATABRICKS_AUTH_TYPE: github-oidc`:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: prod          # must match the subject claim in the federation policy
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@main
      - run: databricks bundle deploy --target prod
```

**Key details that trip people up:**
- The `environment:` key in the workflow job must exactly match the entity type and name in the federation policy subject claim. If the policy says `environment:prod` but the workflow has no `environment:` key or uses `environment:Prod` (case matters), OIDC validation fails with a cryptic auth error.
- `DATABRICKS_CLIENT_ID` is the UUID (e.g. `a1b2c3d4-...`), not the numeric SP ID used in the CLI command.
- Do not set `DATABRICKS_AUTH_TYPE: azure-client-secret` alongside OIDC variables — this forces PAT/secret auth and bypasses OIDC entirely.

**Detection:** Auth failures with OIDC usually surface as `Error: authentication is not configured` or `oidc token exchange failed`. Check that the federation policy subject exactly matches the workflow's `environment:` field.

---

### Pitfall 2: schema Resources Ignore run_as — Deployment Identity Becomes Schema Owner

**What goes wrong:** You configure `run_as` with a service principal in `databricks.yml` so your jobs run under the SP identity. You assume this also makes the SP the owner of Unity Catalog schemas created by the bundle. It does not. Schema ownership is always the deployment user (the identity that runs `databricks bundle deploy`), and `run_as` is silently ignored for schema operations.

**Why it happens:** This is an undocumented gotcha buried in the DABs resources docs. The `run_as` setting only applies to job and pipeline runtime identity, not to resource creation.

**Consequences:** If a human developer runs the initial deploy locally, their personal account becomes the schema owner. The CI/CD service principal cannot then manage that schema. Schema grants fail with `PERMISSION_DENIED`. In dev environments, multiple developers get their own schema copies instead of a shared one, causing confusion.

**Prevention:**
- Always deploy from CI/CD (the SP identity), never from a developer's local machine, for any target that creates Unity Catalog schemas.
- For `dev` environments where each developer needs an isolated schema, use `${workspace.current_user.short_name}` in the schema name — this is intentional and expected.
- For `prod`, ensure the GitHub Actions SP is the entity running `bundle deploy` so that SP is schema owner from day one.
- Grant the SP `USE CATALOG`, `CREATE SCHEMA` on the catalog, and `USE SCHEMA`, `CREATE TABLE`, `MODIFY` on any schemas it needs to manage. See Pitfall 4.

**Detection warning sign:** A schema owned by `user@company.com` that should be owned by a service principal. Check with `SHOW GRANTS ON SCHEMA lol_analytics.bronze`.

---

### Pitfall 3: Forgetting to Set root_path in Production Mode — Collision Across Deployments

**What goes wrong:** In `mode: development`, DABs automatically sets the deploy root to the current user's home directory (`/Workspace/Users/<user>/.bundle/...`). In `mode: production`, if you do not explicitly set `root_path`, the default path is shared and any developer or CI run with deploy access can overwrite each other's artifacts.

**Why it happens:** Developers test locally in dev mode, which works because the user-scoped path prevents collisions. They never think about what happens when two CI runs hit prod simultaneously.

**Consequences:** Race condition between concurrent deploys. State file corruption. The bundle tracks deployed resource IDs in a state file at `root_path`; if two deploys race for the same path, resources get orphaned and re-created on every run.

**Prevention:** Always set an explicit `root_path` in your production target:

```yaml
targets:
  prod:
    mode: production
    workspace:
      host: ${var.prod_host}
      root_path: /Workspace/Shared/.bundle/${bundle.name}/${bundle.target}
    run_as:
      service_principal_name: <SP_APP_ID>
```

Use `concurrency: 1` at the GitHub Actions job level to serialize deploys:

```yaml
jobs:
  deploy:
    concurrency:
      group: prod-deploy
      cancel-in-progress: false
```

**Detection:** Look for jobs appearing twice in the Databricks workspace under slightly different names, or `bundle deploy` taking unexpectedly long due to lock contention.

---

### Pitfall 4: Unity Catalog Permission Gaps That Block CI/CD Deploys

**What goes wrong:** The service principal has workspace access but not the right Unity Catalog grants, causing the deploy to fail at the first table creation or schema access with `PERMISSION_DENIED`.

**Why it happens:** Unity Catalog has a hierarchical permission model. Granting access at the catalog level does not automatically propagate to schemas or tables in all operations. Each level must be granted separately. The CI/CD SP is often set up with only workspace-level "Can Run" or "Can Use" without touching UC at all.

**Required grants for the CI/CD service principal (minimum for this project):**

```sql
-- Account-level: SP must be added to the Databricks account and workspace first

-- Metastore level (done once by metastore admin)
GRANT CREATE CATALOG ON METASTORE TO `<sp-app-id>`;
-- OR if catalog already exists:
GRANT USE CATALOG ON CATALOG lol_analytics TO `<sp-app-id>`;
GRANT CREATE SCHEMA ON CATALOG lol_analytics TO `<sp-app-id>`;

-- Schema level (for each schema the pipeline writes to)
GRANT USE SCHEMA ON SCHEMA lol_analytics.bronze TO `<sp-app-id>`;
GRANT CREATE TABLE ON SCHEMA lol_analytics.bronze TO `<sp-app-id>`;
GRANT MODIFY ON SCHEMA lol_analytics.bronze TO `<sp-app-id>`;
-- Repeat for silver, gold

-- External location (if writing to ADLS Gen2 via external location)
GRANT READ FILES ON EXTERNAL LOCATION `<location_name>` TO `<sp-app-id>`;
GRANT WRITE FILES ON EXTERNAL LOCATION `<location_name>` TO `<sp-app-id>`;
```

**The privilege chain that trips people up:**
- `CREATE TABLE` requires `USE SCHEMA` on the parent schema AND `USE CATALOG` on the parent catalog. Granting `CREATE TABLE` without `USE SCHEMA` silently passes validation but fails at runtime.
- The SP that creates a table becomes its owner. If you later change which identity deploys, you may get a second table owner, and MODIFY from the first SP stops working.
- Cluster policies can additionally restrict which users/SPs can use certain cluster types. The CI/CD SP must be granted CAN_USE on the cluster policy used in the bundle.

**Detection:** `PERMISSION_DENIED: User does not have CREATE TABLE privilege on Schema` during bundle deploy. Use `databricks bundle validate` to catch config errors pre-deploy, but note it does not validate UC permissions — those only surface at runtime.

---

### Pitfall 5: DBFS Mounts Are Incompatible with Unity Catalog — Use Volumes or External Locations

**What goes wrong:** Notebooks use `dbutils.fs.ls("dbfs:/mnt/datalake/...")` paths, which work fine in classic Databricks. When Unity Catalog is enabled (which is the case for this project), mounted storage and DBFS paths are deprecated and not accessible to UC-governed compute by default.

**Why it happens:** Most PySpark tutorials and Stack Overflow answers from before 2023 use DBFS mount patterns. First-timers copy those patterns.

**Consequences:** Silent data access failures. UC-enabled clusters running in "single user" or "shared" access mode cannot read DBFS mount paths. Data appears to not exist even though the files are there.

**The Unity Catalog storage access hierarchy (what to use instead):**

| Pattern | Verdict | Use When |
|---------|---------|----------|
| `dbfs:/mnt/...` | Deprecated, UC-incompatible | Never in new projects |
| `abfss://...` direct path | Works but ungoverned | Emergency only |
| UC External Location + External Table | Correct for existing ADLS data | Raw Bronze landing zone with pre-existing data |
| UC Managed Volume | Correct for UC-managed files | Intermediate/temp files within the lakehouse |
| UC External Volume | Correct for ADLS data needing file-level access | When you need `dbutils.fs` semantics under UC governance |
| UC Managed Table (Delta) | Correct for all Silver/Gold | Default for all structured data |

**For this project (Medallion on Azure with UC):**
- Bronze raw JSON: write to UC managed tables using `spark.write.format("delta")` with full three-part names (`lol_analytics.bronze.match_raw`). Do not land to ADLS files first.
- If landing to ADLS files is required (e.g., raw API dump before parsing): create an External Location backed by ADLS Gen2, then create an External Volume on it. Access via `/Volumes/lol_analytics/bronze/raw/...` paths.
- Never use `dbutils.mount()`. Never use `spark.conf.set("fs.azure.account.key...")` directly in notebooks — use the External Location / managed identity pattern configured at workspace level.

**ADLS Gen2 identity gotcha:** External Locations on Azure must be backed by a Storage Credential that uses a managed identity or service principal registered in the Databricks account. The Azure resource must have "Storage Blob Data Contributor" RBAC assigned to that managed identity on the ADLS Gen2 storage account. Assigning it at the container level is not always sufficient — assign at the storage account level or at the specific container with explicit RBAC propagation enabled.

**Detection:** `Error: This Delta version requires the cluster to be in single user mode` or `DELTA_MISSING_TRANSACTION_LOG` when using DBFS paths from UC-enabled clusters.

---

### Pitfall 6: DABs YAML Schema Mistakes — The Most Common Config Errors

**What goes wrong:** The bundle config fails validation or deploys incorrectly due to structural YAML mistakes. `databricks bundle validate` catches many but not all of these.

**Common structural mistakes:**

**a) cluster_key vs existing_cluster_id confusion**

DABs jobs reference clusters in two ways. In job task definitions, the field is `existing_cluster_id` (for interactive clusters) or `new_cluster` (for ephemeral job clusters). There is no top-level `cluster_key` field in job definitions — that concept comes from older Databricks YAML notations and confuses people who have read mixed documentation.

```yaml
# WRONG — cluster_key does not exist at this level
resources:
  jobs:
    ingestion_job:
      tasks:
        - task_key: bronze_ingest
          cluster_key: my_cluster    # This field is invalid

# CORRECT — reference a cluster defined in the bundle
resources:
  clusters:
    job_cluster:
      spark_version: 15.4.x-scala2.12
      node_type_id: Standard_DS3_v2
      num_workers: 2

  jobs:
    ingestion_job:
      job_clusters:
        - job_cluster_key: main_cluster
          new_cluster:
            spark_version: 15.4.x-scala2.12
            node_type_id: Standard_DS3_v2
            num_workers: 2
      tasks:
        - task_key: bronze_ingest
          job_cluster_key: main_cluster   # References the job_clusters entry above
```

**b) Target naming conflicts with resource name prefixes**

In `mode: development`, DABs prefixes all resource names with `[dev <username>]`. If any downstream code or external system references the resource by its exact name (e.g., the job name in a monitoring dashboard), it will break in dev. Do not hardcode resource names anywhere outside the bundle config.

**c) Missing `default: true` on the dev target**

Without `default: true` on the dev target, every local `bundle deploy` command requires `-t dev` explicitly. Developers forget and accidentally deploy to the wrong target. Make `dev` the default:

```yaml
targets:
  dev:
    mode: development
    default: true
    workspace:
      host: ${var.dev_host}
```

**d) Variable vs job parameter confusion**

DABs variables (`${var.my_var}`) are resolved at deploy time and baked into the deployed job definition. They cannot be changed at runtime without re-deploying. If you need runtime-configurable values (region, tier in this project), use Databricks Job Parameters, not bundle variables:

```yaml
resources:
  jobs:
    ingestion_job:
      parameters:
        - name: region
          default: KR
        - name: tier
          default: CHALLENGER
```

Job parameters are passed at run time: `databricks bundle run ingestion_job --python-params '["region=NA1", "tier=DIAMOND"]'`

**e) Production mode enforces git branch**

In `mode: production`, DABs validates that the currently checked-out git branch matches the branch declared in the target. If the CI runner checks out a detached HEAD (common with `actions/checkout@v4` on tag events), the validation fails. Fix:

```yaml
# In the GitHub Actions workflow
- uses: actions/checkout@v4
  with:
    ref: ${{ github.ref }}

# In databricks.yml
targets:
  prod:
    mode: production
    git:
      branch: main
```

Or use `--force` flag during deploy only if you understand the implications (bypasses branch check).

---

## Moderate Pitfalls

### Pitfall 7: Testing PySpark Without a Live Cluster — Wrong Approach

**What goes wrong:** Developers either (a) skip unit tests entirely because "PySpark needs a cluster", or (b) write tests that hit the real Databricks workspace, making CI slow and expensive.

**The correct local testing stack for Linux:**

```
pyspark          # installs a local Spark runtime, no cluster needed
pytest           # test runner
chispa           # DataFrame equality assertions with readable diffs
pytest-mock      # mock Databricks-specific APIs (dbutils, secrets)
```

Install:

```bash
pip install pyspark chispa pytest pytest-mock
```

**Architecture principle — extract and test pure functions:**

Do not test notebooks directly. Extract transformation logic into pure Python functions that accept and return DataFrames. Test those functions.

```python
# src/transformations/silver/match.py
def flatten_match_participants(df: DataFrame) -> DataFrame:
    """Explode the participants array and select all 147 fields."""
    return (
        df.select(explode("info.participants").alias("p"))
          .select("p.*")
    )
```

```python
# tests/test_match_transformations.py
from pyspark.sql import SparkSession
from chispa import assert_df_equality
from src.transformations.silver.match import flatten_match_participants

def test_flatten_match_participants(spark):
    input_data = [{"info": {"participants": [{"championId": 1, "kills": 5}]}}]
    input_df = spark.createDataFrame(input_data)
    result = flatten_match_participants(input_df)
    assert result.columns == ["championId", "kills"]
    assert result.count() == 1
```

**conftest.py (session-scoped SparkSession for fast CI):**

```python
# tests/conftest.py
import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("test_suite")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.executor.cores", "1")
        .getOrCreate()
    )
    yield session
    session.stop()
```

**Mocking dbutils:**

```python
# tests/conftest.py (additional fixture)
@pytest.fixture
def mock_dbutils(mocker):
    dbutils = mocker.MagicMock()
    dbutils.secrets.get.return_value = "fake-api-key"
    return dbutils
```

**Running locally on Linux:**

```bash
# Set JAVA_HOME (PySpark requires Java 8 or 11)
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

# Run tests
pytest tests/ -v --tb=short
```

Java is required for PySpark local mode. On Linux Mint: `sudo apt install openjdk-11-jdk`.

**What NOT to use:**
- `databricks-test` (PyPI) — unmaintained, designed for older Databricks runtime versions.
- Databricks Connect for unit tests — correct for integration tests but overkill for pure transformation logic; it still requires a running cluster.
- `delta-rs` (Rust-backed Delta Lake) — useful for reading Delta tables without Spark in Python scripts, but cannot run Spark transformations. Use only for schema inspection, not testing Spark logic.

---

### Pitfall 8: Pinning `databricks/setup-cli@main` in Production Pipelines

**What goes wrong:** Using `@main` in `databricks/setup-cli@main` means the CI always pulls the latest CLI version. A breaking CLI change (schema changes, flag renames) can break prod deploys with zero code changes from your side.

**Prevention:** Pin to a specific release version in production workflows:

```yaml
- uses: databricks/setup-cli@v0.240.0   # pin to a known good version
```

Use `@main` only in a dedicated "upgrade test" workflow that runs weekly against a non-production target.

---

### Pitfall 9: Hardcoding Workspace Host in databricks.yml Instead of Using Variables

**What goes wrong:** Developers hardcode the dev workspace URL directly in `databricks.yml`. When they need to add a staging environment, the YAML requires edits instead of just adding a new target.

**Prevention:** Always use bundle variables for workspace hosts:

```yaml
variables:
  dev_host:
    description: Dev workspace URL
    default: https://adb-<dev-id>.azuredatabricks.net
  prod_host:
    description: Production workspace URL
    default: https://adb-<prod-id>.azuredatabricks.net

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: ${var.dev_host}
  prod:
    mode: production
    workspace:
      host: ${var.prod_host}
```

Override at deploy time in CI: `databricks bundle deploy --target prod --var "prod_host=${{ vars.PROD_HOST }}"`.

---

## Minor Pitfalls

### Pitfall 10: Riot API Key Stored as Environment Variable Instead of Databricks Secret

**What goes wrong:** The Riot API key (24h dev key or permanent production key) is set as a GitHub Actions secret and injected as an environment variable into the notebook. This means the key is visible in cluster environment variable listings and job run logs.

**Prevention:** Store the key in Databricks Secrets:

```bash
databricks secrets create-scope lol-pipeline
databricks secrets put-secret lol-pipeline riot-api-key --string-value "<key>"
```

In notebooks:

```python
api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
```

The CI/CD SP needs `CAN_READ` on the secret scope, granted by the scope owner via the Secrets ACL.

---

### Pitfall 11: Development Mode Resource Prefix Breaks Job Run Commands in CI

**What goes wrong:** In `mode: development`, all jobs are prefixed with `[dev <username>]`. A CI script that runs `databricks bundle run ingestion_job` works because DABs looks up by the logical name. But scripts that call `databricks jobs run-now --job-id <id>` using a hardcoded ID from the workspace break when the job is recreated with a new ID on next deploy.

**Prevention:** Always reference jobs by logical name via `databricks bundle run <job_name>`, never by workspace job ID. Never hardcode job IDs in any script.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Infrastructure setup | SP added to workspace but not account | Add SP at account level first, then workspace |
| First bundle deploy | OIDC subject claim mismatch | Match `environment:` in workflow to federation policy exactly |
| Bronze ingestion | Using DBFS paths for raw data | Use `lol_analytics.bronze.*` UC managed tables or UC External Volume |
| Silver transformations | Testing requires live cluster | Extract to pure functions; test locally with `pyspark` + `chispa` |
| Unity Catalog schemas | Schema owned by developer, not SP | Always deploy prod target from CI, never from local machine |
| Job parameters | Using bundle variables for region/tier | Use Databricks Job Parameters for runtime values, not bundle vars |
| Production CI deploy | SP missing `MODIFY` on schema | Grant full privilege chain: USE CATALOG → USE SCHEMA → CREATE TABLE → MODIFY |
| Secret management | API key in env vars | Databricks Secrets scope, grant CAN_READ to CI SP |

---

## Recommended Repository Structure (Opinionated)

This layout maximizes enterprise impression for a portfolio project while being functional for real CI/CD:

```
dbx-mls/
├── databricks.yml                    # Root bundle config — bundle name, includes, targets
├── resources/                        # All Databricks resource definitions (jobs, clusters, schemas)
│   ├── schemas.yml                   # UC schema declarations (bronze, silver, gold)
│   ├── clusters.yml                  # Reusable cluster configs
│   ├── jobs/
│   │   ├── ingestion_job.yml         # Bronze ingestion job
│   │   └── transformation_job.yml    # Silver transformation job
├── src/                              # All Python source code
│   ├── ingestion/                    # Bronze layer notebooks / modules
│   │   ├── bronze_league_entries.py
│   │   ├── bronze_match_raw.py
│   │   └── riot_api_client.py        # API client with rate limiting
│   ├── transformations/              # Silver layer logic (pure functions, testable)
│   │   ├── silver_match.py
│   │   ├── silver_match_participants.py
│   │   └── silver_timeline.py
│   └── common/                       # Shared utilities (schema helpers, logger)
│       ├── config.py
│       └── logger.py
├── tests/                            # pytest test suite
│   ├── conftest.py                   # SparkSession fixture, mock_dbutils fixture
│   ├── unit/                         # Pure function tests (no cluster)
│   │   ├── test_silver_match.py
│   │   └── test_silver_participants.py
│   └── integration/                  # Post-deploy tests against dev workspace
│       └── test_bronze_ingestion.py
├── .github/
│   └── workflows/
│       ├── ci.yml                    # validate + pytest on every PR
│       └── cd.yml                    # deploy-dev on push to main, deploy-prod on tag
├── pyproject.toml                    # Package definition, pytest config, dev dependencies
└── Makefile                          # Local shortcuts: make test, make validate, make deploy-dev
```

**Rationale:**

- `resources/` separated from `src/` mirrors the DABs default template and makes it immediately clear what is Databricks infrastructure vs application code. Hiring managers who know DABs recognize this layout.
- `resources/` uses `include:` in `databricks.yml` (`include: resources/*.yml`, `include: resources/jobs/*.yml`), so each resource type is in its own file — avoids a 500-line monolithic `databricks.yml`.
- `src/transformations/` contains only pure Python functions (no `display()`, no `dbutils` calls). This is the testable layer.
- `tests/unit/` runs in CI with zero cluster cost. `tests/integration/` runs post-deploy against the `dev` target only (never `prod`).
- `pyproject.toml` over `setup.py` or `requirements.txt` — the modern Python standard, signals engineering hygiene.
- `Makefile` is not required but adds "onboarding in 30 seconds" value for reviewers who clone the repo.

---

## Sources

- [GitHub Actions - Azure Databricks (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/github) — Official workflow examples (PAT and OIDC)
- [Enable workload identity federation for GitHub Actions (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/provider-github) — Federation policy setup, subject claim format
- [Authentication for Declarative Automation Bundles (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/authentication) — Auth modes for bundles
- [DABs Deployment Modes (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/deployment-modes) — dev vs prod mode behaviors, root_path, presets
- [DABs Resources (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/resources) — Schema ownership limitation (run_as ignored)
- [Manage privileges in Unity Catalog (Databricks docs)](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/) — Permission hierarchy
- [Databricks mounts deprecated (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dbfs/mounts) — Official deprecation notice
- [What are Unity Catalog volumes? (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/volumes/) — Volume vs mount guidance
- [DABs Substitutions and variables (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/variables) — Variable vs job parameter distinction
- [MrPowers/chispa (GitHub)](https://github.com/MrPowers/chispa) — PySpark DataFrame testing library
- [Testing PySpark Code (MungingData)](https://www.mungingdata.com/pyspark/testing-pytest-chispa/) — chispa + pytest patterns
- [Specify a run identity for DABs (Databricks docs)](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as) — run_as behavior and limitations
