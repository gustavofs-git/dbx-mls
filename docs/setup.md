# Setup Guide — dbx-mls

This is a lean reference guide for reproducing the `dbx-mls` pipeline in your own Azure Databricks workspace. It assumes you already have an Azure subscription and know how to provision a Databricks workspace. It is not a step-by-step tutorial.

---

## Prerequisites

- Azure subscription with an Azure Databricks workspace (Unity Catalog enabled)
- Databricks CLI v0.295.0+ installed locally
- GitHub repository forked or cloned from this repo
- GitHub account with admin access to the repository

> **Important:** The author's clusters are private and cost-incurring. You cannot connect to them.
> To run this pipeline, provision your own Azure Databricks workspace and bear the Azure compute costs.

### Cost Estimate

All jobs use `Standard_F4s_v2` (4 vCPUs, 8 GB RAM).

| Activity | Estimated Cost |
|---|---|
| Smoke test run (single job) | ~$0.05–0.10 |
| Full Phase 1 deploy + smoke test | ~$0.50–1.00 |
| **Total Phase 1 setup run** | **Under $5** |

Costs are based on Azure East US pricing as of Q1 2026. Actual costs vary by region and current Azure spot pricing.

---

## 1. OIDC Federation Setup

This pipeline uses OIDC Workload Identity Federation — no long-lived PAT tokens or secrets. GitHub Actions exchanges a short-lived OIDC token directly with Databricks.

### Step 1: Create Service Principal

1. Log in to the [Databricks Account Console](https://accounts.azuredatabricks.net)
2. Go to **User management → Service Principals → Add service principal**
3. Note two IDs:
   - **Application (client) ID** — UUID format (e.g. `a1b2c3d4-...`) — used in GitHub variables and UC grants
   - **Numeric SP ID** — integer (e.g. `1234567890123456`) — used in federation policy CLI commands

### Step 2: Authenticate CLI to Account Console

```bash
databricks auth login --host https://accounts.azuredatabricks.net --account-id <ACCOUNT_ID>
```

Find your `<ACCOUNT_ID>` in the Databricks Account Console → top-right user menu → Account ID.

### Step 3: Create Dev Federation Policy (Branch-Scoped)

This policy allows GitHub Actions to authenticate when running on the `main` branch. Replace `<org>` with your GitHub organization or username, and `<SP_NUMERIC_ID>` with the integer SP ID from Step 1.

```bash
databricks account service-principal-federation-policy create <SP_NUMERIC_ID> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["https://github.com/<org>"],
    "subject": "repo:<org>/dbx-mls:ref:refs/heads/main"
  }
}'
```

### Step 4: Create Prod Federation Policy (Environment-Scoped)

This policy allows GitHub Actions to authenticate when running in the `prod` GitHub Environment.

```bash
databricks account service-principal-federation-policy create <SP_NUMERIC_ID> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["https://github.com/<org>"],
    "subject": "repo:<org>/dbx-mls:environment:prod"
  }
}'
```

> **Warning — case-sensitive match:** The `environment: prod` key in `cd-prod.yml` and the string `environment:prod` in the federation policy subject claim are CASE-SENSITIVE and must match exactly. A mismatch produces a cryptic 401 with no clear error message. Double-check both are lowercase `prod`.

### Step 5: Add Repository Variables in GitHub

These are repository **variables** (not secrets) — no sensitive data.

1. Go to: **GitHub repo → Settings → Secrets and variables → Actions → Variables tab**
2. Add `DATABRICKS_HOST` — value: `https://adb-<workspace-id>.<region>.azuredatabricks.net`
3. Add `DATABRICKS_CLIENT_ID` — value: the UUID application ID of the service principal

### Step 6: Create GitHub Environment `prod`

1. Go to: **GitHub repo → Settings → Environments → New environment**
2. Name it exactly `prod` (lowercase — must match the federation policy subject)
3. Under **Protection rules**, add yourself as a **Required reviewer**

### Step 7: Add SP to Databricks Workspace

1. Go to: **Databricks workspace → Settings → Identity and access → Service principals**
2. Add the SP and assign it sufficient workspace permissions (at minimum **Can Manage** on the workspace, or role-specific permissions as needed)

---

## 2. Unity Catalog Grant SQL

A workspace admin must run these SQL statements **once** before the first CI deploy. This grants the service principal permission to deploy schemas and create tables.

> **Critical:** NEVER run `databricks bundle deploy` locally before the SP deploys via CI. The first deploy sets schema ownership. If a developer runs it first, the human user becomes schema owner — this is extremely difficult to fix without dropping the schemas.

Run in a Databricks notebook or SQL Editor as a workspace admin:

```sql
GRANT USE CATALOG   ON CATALOG lol_analytics                TO `<sp-application-id>`;
GRANT CREATE SCHEMA ON CATALOG lol_analytics                TO `<sp-application-id>`;
GRANT USE SCHEMA    ON SCHEMA lol_analytics.bronze          TO `<sp-application-id>`;
GRANT CREATE TABLE  ON SCHEMA lol_analytics.bronze          TO `<sp-application-id>`;
GRANT MODIFY        ON SCHEMA lol_analytics.bronze          TO `<sp-application-id>`;
GRANT USE SCHEMA    ON SCHEMA lol_analytics.silver          TO `<sp-application-id>`;
GRANT CREATE TABLE  ON SCHEMA lol_analytics.silver          TO `<sp-application-id>`;
GRANT MODIFY        ON SCHEMA lol_analytics.silver          TO `<sp-application-id>`;
GRANT USE SCHEMA    ON SCHEMA lol_analytics.gold            TO `<sp-application-id>`;
GRANT CREATE TABLE  ON SCHEMA lol_analytics.gold            TO `<sp-application-id>`;
GRANT MODIFY        ON SCHEMA lol_analytics.gold            TO `<sp-application-id>`;
```

Replace `<sp-application-id>` with the UUID application ID (not the numeric ID).

**Verify ownership after first deploy:**

```sql
SHOW GRANTS ON SCHEMA lol_analytics.bronze
```

The output must show the SP application ID as the owner — not a human email address. If you see a human email, the schema was created by a developer locally and ownership must be corrected before continuing.

---

## 3. Riot API Key Rotation

The Riot Games development API key expires every 24 hours. You must rotate it before each pipeline run.

### Get a Dev Key

1. Log in to [developer.riotgames.com](https://developer.riotgames.com)
2. A development key is shown on the dashboard — it auto-regenerates every 24 hours

### Store in Databricks Secrets

Create the scope and store the key (run once for scope creation, re-run `put-secret` for each rotation):

```bash
databricks secrets create-scope lol-pipeline
databricks secrets put-secret lol-pipeline riot-api-key --string-value "<YOUR_KEY>"
databricks secrets put-acl lol-pipeline "<sp-application-id>" READ
```

### Rotation Process

When the key expires, re-run only the `put-secret` command — no scope recreation needed:

```bash
databricks secrets put-secret lol-pipeline riot-api-key --string-value "<NEW_KEY>"
```

### Permanent Key

For continuous operation without 24-hour rotation, register a production application at [developer.riotgames.com/app-registration](https://developer.riotgames.com/app-registration). Production keys have no expiry but require application review by Riot Games.

---

## 4. Local Dev Environment

### Databricks CLI

```bash
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
databricks auth login --host <workspace-url>
```

Verify: `databricks --version` should show `0.295.0` or higher.

### Python Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Java 11 (required for local PySpark in pytest)

Local `pytest` runs PySpark which requires a JVM. Install Java 11:

```bash
sudo apt-get install openjdk-11-jdk
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
```

Add the `export JAVA_HOME=...` line to your `.bashrc` or `.zshrc` to persist it.

### Make Targets

| Target | What it does |
|---|---|
| `make validate` | Runs `databricks bundle validate` |
| `make test` | Runs `pytest tests/unit/` with coverage |
| `make smoke` | Runs `databricks bundle run smoke_test_job --target dev` |

Run `make validate` before any push to catch bundle config errors locally.
