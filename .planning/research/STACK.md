# Technology Stack

**Project:** dbx-mls — Databricks Modern Lakehouse (League of Legends)
**Researched:** 2026-04-07
**Confidence:** HIGH (verified against official Microsoft/Databricks docs and PyPI, April 2026)

---

## Recommended Stack

### Databricks Runtime

**Recommendation: DBR 16.4 LTS**

| Property | Value |
|----------|-------|
| Version | 16.4 LTS |
| Apache Spark | 3.5.2 |
| Python | 3.12.3 |
| Scala | 2.13 (use 2.13 image, not 2.12) |
| Release date | May 2025 |
| End-of-support | May 2028 |

**Why 16.4 LTS over 17.3 LTS:**

DBR 17.3 LTS (Spark 4.0, released Oct 2025) is the latest LTS and is production-quality, but it introduces non-trivial breaking changes for new projects:

- `input_file_name()` is removed — use `_metadata.file_name` instead
- `cloudFiles.useIncrementalListing` default changed to `false`
- Scala 2.12 is completely dropped (Scala 2.13 only)
- Some Spark Connect behavioral changes around decimal precision and null handling

For a greenfield Python/PySpark project with no Scala code, 17.3 LTS is viable but adds upgrade risk with no benefit. DBR 16.4 LTS has a 3-year support window (to May 2028), ships Python 3.12.3, and is the safer portfolio choice. If the project extends into mid-2026 or later, migrate to 17.3 LTS at the next natural phase boundary.

**Why NOT 15.4 LTS:** Older Python (3.11), less time on support window, missing newer Delta/UC features like Auto Loader type widening.

**Why NOT 18.x (non-LTS):** Short 6-month support window — not appropriate for a portfolio project meant to demonstrate production patterns.

Source: [Azure Databricks Runtime release notes — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/)

---

### IaC and Deployment: Databricks Asset Bundles (DABs)

| Property | Value |
|----------|-------|
| CLI version | 0.295.0+ (latest as of March 2026) |
| Config format | `databricks.yml` (YAML, no explicit schema version field) |
| CLI pin in bundle | `bundle.databricks_cli_version: ">=0.250.0"` |
| Targets | `dev` (default), `prod` |

**DABs vs Terraform — when to use which:**

| Tool | Use For | Don't Use For |
|------|---------|---------------|
| **DABs** | Jobs, workflows, notebooks, clusters, schemas, secret scopes, volumes — anything inside the workspace | Workspace provisioning, network config, ADLS Gen2 containers, Access Connectors |
| **Terraform** | Azure infrastructure: workspace itself, ADLS Gen2, Access Connector, network rules, Key Vault | Per-job parameters, notebook deployment, environment promotion |

**Verdict for this project:** DABs handle 100% of what this project needs. Workspace provisioning is a one-time manual step documented in Phase 1. Terraform would add complexity with no benefit for a single-developer portfolio project. Use DABs.

**Why NOT plain notebooks as IaC:** No version control of cluster config, no environment promotion, no `bundle validate`, no CI integration.

**Why NOT Databricks Terraform Provider alone:** Platform engineers' tool. Data Engineering roles don't use it in interviews. DABs are the expected DE pattern.

DABs have been renamed "Declarative Automation Bundles" in CLI v0.295.0 but the concept and YAML structure are identical. The name "DABs" remains in wide community use.

Source: [Declarative Automation Bundles configuration — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/settings)

---

### Python Environment (Local / CI)

| Property | Value |
|----------|-------|
| Python version | 3.12 (matches DBR 16.4 LTS bundled version) |
| Package manager | `pip` with `requirements.txt` (simplest for CI); Poetry optional for local |
| Virtual env | `venv` or `uv` |

**Why Python 3.12:** Exact match to the DBR 16.4 LTS bundled interpreter (3.12.3). Mismatching local and cluster Python versions causes subtle serialization bugs with PySpark UDFs and Pandas UDFs. Python 3.12 is also actively supported until Oct 2028.

---

### Core Libraries

#### PySpark (local testing)

| Library | Version | Why |
|---------|---------|-----|
| `pyspark` | `3.5.2` | Matches Spark version in DBR 16.4 LTS. Install locally for unit tests only — never used in cluster jobs (cluster has its own Spark). |

**Critical constraint:** Do NOT import `pyspark` in production cluster code as an explicit dependency. The cluster runtime provides it. `pyspark` in `requirements.txt` is for local testing only — separate it into a `requirements-dev.txt` or `pyproject.toml` dev group.

#### Databricks SDK

| Library | Version | Why |
|---------|---------|-----|
| `databricks-sdk` | `>=0.102.0` | Latest stable (March 2026). Use for workspace API calls, secret management, job triggering in CI. Replaces direct REST API calls. |

**Why the SDK over raw REST:** Type-safe, auto-paginates, handles auth transparently (works with SP tokens, Azure CLI auth, PATs). The SDK is what `databricks bundle` uses internally.

#### Delta Lake

| Library | Version | Why |
|---------|---------|-----|
| `delta-spark` | `3.3.2` (stable) or `4.0.0` (preview, matches Spark 4) | DBR 16.4 (Spark 3.5.2) → use `delta-spark==3.3.2` for local SparkSession in tests. DBR embeds Delta Lake natively; `delta-spark` is test-only. |

**Note:** In cluster code, Delta is already available. `delta-spark` is for constructing a local `SparkSession` with Delta support in unit tests.

#### Azure Integration

| Library | Version | Purpose |
|---------|---------|---------|
| `azure-identity` | `>=1.19.0` | Managed identity / Service Principal auth for Azure resources from local dev and CI |
| `azure-keyvault-secrets` | `>=4.9.0` | Direct Key Vault access if using Unity Catalog Service Credentials pattern |

**Important:** In production cluster code, you do NOT call Azure SDK directly for storage. Unity Catalog handles ADLS Gen2 access through Access Connector + managed identity. These libraries are for local dev tooling and CI scripts that need to call Azure APIs.

#### HTTP and Rate Limiting (Riot API Client)

| Library | Version | Purpose |
|---------|---------|---------|
| `requests` | `>=2.32.0` | HTTP client for Riot API calls |
| `tenacity` | `>=9.0.0` | Retry with exponential backoff — the standard for rate-limit handling |

**Why tenacity over backoff or urllib3.Retry:** Tenacity is the de facto Python retry standard. It supports `@retry` decorator with `wait_exponential`, `wait_random_exponential`, `retry_if_exception_type(RateLimitError)`, and `stop_after_attempt`. It composes cleanly with Databricks notebook code. Riot Dev key (20 req/s, 100 req/2min) requires per-call rate limiting, not just connection retries.

#### Testing

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=8.3.0` | Test runner — industry standard, supports fixtures, parametrize, CI output |
| `chispa` | `>=0.9.4` | PySpark DataFrame assertion helper — descriptive diffs showing exactly which rows differ |
| `pytest-cov` | `>=6.0.0` | Coverage reporting for CI |

**Testing strategy — two-track:**

1. **Unit tests (no cluster required):** Pure Python transformation logic extracted into functions that take DataFrames as arguments. Uses `pyspark` local mode (`SparkSession.builder.master("local[*]")`). Run in GitHub Actions with zero Databricks dependency. These are the primary test surface.

2. **Integration tests (cluster required):** Post-deploy validation against `dev` environment. Run `databricks bundle run test_job -t dev`. Validates end-to-end from API call to Delta table write.

**Why NOT `databricks-connect` for unit tests:** Databricks Connect requires a live workspace connection, which makes tests slow (~10-30s startup) and requires credentials in CI. For transformation logic, local PySpark is faster and simpler. Databricks Connect is useful for interactive development in VS Code, not automated unit tests.

**Why NOT pytest-spark:** Unmaintained, adds no value over a plain `conftest.py` SparkSession fixture.

---

### CI/CD: GitHub Actions

| Component | Choice | Version/Detail |
|-----------|--------|---------------|
| CLI setup action | `databricks/setup-cli` | `@main` (recommended by official docs) |
| Python setup | `actions/setup-python` | `@v5`, python-version: `"3.12"` |
| Validation step | `databricks bundle validate` | Via CLI |
| Deploy step | `databricks bundle deploy -t dev` | Via CLI |
| Auth method | Service Principal with `DATABRICKS_HOST` + `DATABRICKS_TOKEN` secrets | PAT or SP OAuth |

**Pipeline pattern:**
```
push → validate → pytest (unit) → bundle deploy -t dev → integration test (bundle run)
release tag → manual approval → bundle deploy -t prod
```

---

### Storage: ADLS Gen2 + Unity Catalog

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Storage account | ADLS Gen2 with hierarchical namespace | Required for Unity Catalog external locations |
| Access method | Azure Access Connector + Managed Identity assigned to UC | No credentials to rotate, works through storage firewall |
| Unity Catalog external location | One external location per container | Standard pattern |
| Table naming | `lol_analytics.{layer}.{table}` (three-part UC names) | Project requirement, UC standard |

**Never use:** `spark.conf.set("fs.azure.account.key...")` or SAS tokens for cluster-level storage access. These bypass Unity Catalog governance entirely. Managed identity via Access Connector is the only correct pattern.

---

### Secrets Management

**Recommendation: Databricks Secrets (Secret Scopes) for the Riot API key**

Unity Catalog Service Credentials (backed by Azure Key Vault) are the 2025 best practice for _Azure service credentials_ (storage, Key Vault). For application secrets like a Riot Games API key, Databricks Secrets remain the correct tool — they are:

- Accessible inside notebooks/jobs via `dbutils.secrets.get("scope", "key")`
- Redacted automatically in Databricks logs
- Not visible in plain text to any user (even admins see only redacted values)

**Workflow:**
1. Store Riot API key in a Databricks Secret Scope (not AKV-backed for simplicity at this scale)
2. Access in notebooks: `dbutils.secrets.get(scope="lol-analytics", key="riot-api-key")`
3. DABs can reference secrets in job parameters as `{{secrets/lol-analytics/riot-api-key}}`

**Never:** Hardcode API keys. Never pass them as plain job parameters. Never write them to Delta tables.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Runtime | DBR 16.4 LTS | DBR 17.3 LTS | Spark 4.0 breaking changes add migration risk on a greenfield project; re-evaluate at phase 3+ |
| Runtime | DBR 16.4 LTS | DBR 15.4 LTS | Older Python (3.11), shorter support window |
| IaC | DABs | Terraform | Platform engineer tool; overkill for single-developer DE project; DABs are what hiring managers expect |
| IaC | DABs | Plain notebooks | No version control of config, no CI, no environment promotion |
| Retry | tenacity | backoff | Both work; tenacity has more active maintenance and clearer API |
| Retry | tenacity | urllib3.Retry | Only handles HTTP-level retries; Riot API needs application-level rate limiting with sliding window logic |
| Testing | pyspark local | databricks-connect | Connect requires live workspace, slows CI; local PySpark is sufficient for transformation unit tests |
| Auth (storage) | Managed Identity + Access Connector | SAS tokens / account keys | SAS tokens expire, account keys bypass UC governance entirely |
| Secrets | dbutils.secrets | Hardcoded / env vars | Never. Violates project constraints and security fundamentals |

---

## Installation

### `requirements.txt` (production cluster dependencies)

```
requests>=2.32.0
tenacity>=9.0.0
databricks-sdk>=0.102.0
```

### `requirements-dev.txt` (local development and CI)

```
-r requirements.txt
pyspark==3.5.2
delta-spark==3.3.2
pytest>=8.3.0
chispa>=0.9.4
pytest-cov>=6.0.0
azure-identity>=1.19.0
```

### Databricks CLI (local machine)

```bash
curl -fsSL https://raw.githubusercontent.com/databricks/setup-databricks-cli/main/setup.sh | sh
databricks --version  # should be 0.295.0 or later
```

### `databricks.yml` minimum viable header

```yaml
bundle:
  name: dbx-mls
  databricks_cli_version: ">=0.250.0"

targets:
  dev:
    default: true
    workspace:
      host: ${var.workspace_host}
  prod:
    workspace:
      host: ${var.workspace_host_prod}
```

---

## What NOT to Use

| Anti-Pattern | Why | Alternative |
|--------------|-----|-------------|
| `hive_metastore` | Deprecated, not governed, not portable across workspaces | Unity Catalog three-part names only |
| `dbutils.widgets` for job parameters | UI-only, not scriptable, not DABs-native | DAB job `parameters` block |
| Spark `3.4.x` or older runtimes | Out of support before project ends | DBR 16.4 LTS (Spark 3.5.2) |
| `%run ./notebook` for sharing code | Creates hidden dependencies, no testability | Python `.py` files imported as modules |
| `spark.conf.set("fs.azure.account.key...")` | Bypasses UC governance, leaks keys in logs | Managed Identity + Unity Catalog external location |
| Legacy Databricks CLI (pre-0.205) | Doesn't support DABs | Databricks CLI 0.295+ |
| `azure-databricks-sdk-python` (PyPI) | Third-party, unmaintained | Official `databricks-sdk` from Databricks |
| `pytest-spark` | Unmaintained since 2021 | Plain `conftest.py` fixture with `SparkSession.builder.master("local[*]")` |
| `input_file_name()` Spark function | Removed in DBR 17.3+, unreliable even in 16.4 | `_metadata.file_name` |
| Hardcoded cluster IDs in `databricks.yml` | Breaks across workspaces/environments | Named cluster references or `new_cluster` blocks |

---

## Sources

- [Azure Databricks Runtime release notes — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/) — HIGH confidence, official docs, updated March 2026
- [Databricks Runtime 16.4 LTS — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/16.4lts) — HIGH confidence, Python 3.12.3 confirmed
- [Databricks Runtime 17.3 LTS — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/17.3lts) — HIGH confidence, Python 3.12.3, Spark 4.0.0
- [Declarative Automation Bundles configuration — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/settings) — HIGH confidence, official YAML schema
- [databricks-sdk PyPI](https://pypi.org/project/databricks-sdk/) — HIGH confidence, v0.102.0 as of March 2026
- [Databricks CLI releases — GitHub](https://github.com/databricks/cli/releases) — HIGH confidence, v0.295.0 as of March 2026
- [delta-spark PyPI](https://pypi.org/project/delta-spark/) — HIGH confidence, 3.3.2 stable, 4.0.0 available
- [Unity Catalog to Azure Key Vault — sunnydata.ai](https://www.sunnydata.ai/blog/azure-key-vault-unity-catalog-service-credentials) — MEDIUM confidence, community article verified against official UC docs
- [Terraform vs. Databricks Asset Bundles — Alex Ott](https://medium.com/@alexott_en/terraform-vs-databricks-asset-bundles-6256aa70e387) — MEDIUM confidence, practitioner analysis aligns with official guidance
- [GitHub Actions — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/github) — HIGH confidence, official docs
- [tenacity GitHub](https://github.com/jd/tenacity) — HIGH confidence, actively maintained Apache 2.0 library
- [chispa GitHub](https://github.com/MrPowers/chispa) — MEDIUM confidence (PyPI page returned error during fetch; README confirmed via GitHub)
