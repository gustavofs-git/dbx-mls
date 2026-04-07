# Phase 1: Infrastructure, Governance & CI/CD Foundation — Research

**Researched:** 2026-04-07
**Domain:** Azure Databricks DABs, OIDC Workload Identity Federation, Unity Catalog, GitHub Actions CI/CD
**Confidence:** HIGH (all critical paths verified against official Microsoft/Databricks docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Cluster Configuration**
- D-01: Dev and prod job clusters both use `node_type_id: Standard_F4s_v2` (8 GB RAM, 4 vCPUs)
- D-02: `autotermination_minutes: 0` on job clusters (terminate when job finishes — correct job cluster pattern)
- D-03: Both `dev` and `prod` targets use the same VM size

**Smoke Test**
- D-04: Smoke test job (`resources/jobs/smoke_test_job.yml` + `notebooks/smoke_test.py`) is permanent — never removed after Phase 1
- D-05: `cd-dev.yml` auto-triggers smoke test after every successful dev deploy: deploy → run smoke_test_job → assert exit 0
- D-06: Smoke test covers three validations: (1) Riot API key via `dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")`, (2) `SHOW SCHEMAS IN lol_analytics`, (3) Bronze table roundtrip (`lol_analytics.bronze.smoke_test` create/read/drop)

**Setup Documentation (`docs/setup.md`)**
- D-07: Lean reference guide (not tutorial) — assumes reader has an Azure subscription and Databricks workspace
- D-08: Explicitly state author's clusters are private — reviewers provision their own
- D-09: Include cost estimate section with per-run costs for Standard_F4s_v2
- D-10: Must cover four topics: OIDC federation setup, UC grant SQL, Riot API key rotation, local dev environment

**LinkedIn Phase 1 Deliverable**
- D-11: Full story narrative article — covers complete Phase 1 scope
- D-12: Deep-dive with real code snippets (YAML, workflows, federation policy, UC grant SQL)
- D-13: Claude as Robin — engineer's architecture decisions are the hero; Claude gets a paragraph mention
- D-14: Short post ~150 words with OIDC zero-secrets angle as hook

### Claude's Discretion
- Auto-termination policy for any interactive clusters (not applicable in Phase 1 — job clusters only)
- Exact `make` target implementations beyond `validate`, `test`, `smoke`
- `resources/clusters.yml` exact `spark.databricks.cluster.profile` value (singleUser specified in roadmap)
- Order of topics in `docs/setup.md`
- Exact phrasing of cost disclaimer and cost estimate numbers

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within Phase 1 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Azure Databricks workspace provisioned with Unity Catalog enabled | Manual prerequisite; documented in docs/setup.md |
| INFRA-02 | `lol_analytics` catalog with `bronze`, `silver`, `gold` schemas in UC | `resources/schemas.yml` DABs resource; ownership via `ALTER SCHEMA ... OWNER TO` |
| INFRA-03 | Service Principal created, assigned schema ownership from CI (not developer laptop) | SP created at account level; federation policy enables CI-only deploy; `ALTER SCHEMA OWNER TO` run once by admin |
| INFRA-04 | `databricks.yml` defines `dev` and `prod` targets with DBR 16.4 LTS cluster config | DABs reference confirmed; `spark_version: 16.4.x-scala2.12` |
| INFRA-05 | Riot API key stored in Databricks Secret Scope (`lol-pipeline` / `riot-api-key`) | `databricks secrets create-scope` + `put-secret` + `put-acl` CLI commands |
| INFRA-06 | Smoke-test DAB deploy succeeds end-to-end | `databricks bundle run smoke_test_job --target dev` asserted in CD workflow |
| INFRA-07 | `.gitignore` excludes secrets, `.env`, Python artifacts | Standard patterns documented |
| CICD-01 | GitHub Actions `ci.yml` — `databricks bundle validate` + `pytest` on every push | OIDC-authenticated; `id-token: write` permission required |
| CICD-02 | GitHub Actions `cd-dev.yml` — deploys to `dev` on push to `main` | Branch-scoped federation policy; no `environment:` key in job |
| CICD-03 | GitHub Actions `cd-prod.yml` — deploys to `prod` on release tags `v*` with manual approval | Environment-scoped federation policy; `environment: prod` in job; GitHub Environment protection rule |
| CICD-04 | Authentication uses OIDC federation — zero long-lived secrets | Verified against official docs; `DATABRICKS_AUTH_TYPE: github-oidc` |
| CICD-05 | `setup-databricks-cli` action pins CLI version (`>=0.250.0`) | `databricks/setup-cli@v0.295.0` or `@main` with `version: 0.295.0` parameter |
| CICD-06 | Prod deploy job has `concurrency` group to prevent parallel prod deploys | `concurrency: { group: prod-deploy, cancel-in-progress: false }` |
</phase_requirements>

---

## Summary

Phase 1 establishes the complete infrastructure baseline for the `dbx-mls` project: repo scaffold, Databricks Asset Bundles configuration, OIDC Workload Identity CI/CD, Unity Catalog schema ownership, Databricks Secrets, and a permanent smoke-test job. No pipeline code is written — this phase exists solely to prove the deploy path before data work begins.

The critical constraint for this phase is the **schema ownership bootstrap problem**: DABs cannot set a service principal as schema owner via the `run_as` field because schema resources are always owned by the deploying identity. The solution is (1) never run `bundle deploy` locally against any target, and (2) have a workspace admin run the SQL `ALTER SCHEMA ... OWNER TO` command once after the SP deploys the schemas the first time. The SP becomes both the deployer and the owner from day one.

The second critical constraint is **OIDC subject claim case-sensitivity**: the `environment:` key in the GitHub Actions workflow job block must exactly match (including case) the subject claim in the federation policy. This is a silent failure mode — the federation policy just doesn't match and auth fails with a cryptic 401.

**Primary recommendation:** Build in the exact order defined in the four plans (scaffold → OIDC → UC/secrets → smoke test). Do not attempt shortcuts. The dependency chain is real: schemas cannot be owned by the SP until the SP exists (Plan 01-02), and the smoke test cannot run until schemas exist (Plan 01-03).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Databricks CLI | `>=0.295.0` (latest as of 2026-04-07) | Bundle deploy, secrets management, federation policy creation | Required by DABs; OIDC auth support requires >=0.250.0 |
| Databricks Asset Bundles | Built into CLI | IaC for jobs, schemas, clusters | Project decision; no Terraform |
| GitHub Actions `setup-cli` | `v0.295.0` | Install/pin CLI in CI | Official Databricks action |
| `actions/checkout` | `v4` | Repo checkout | Standard; v4 required for tag event `ref` handling |
| `actions/setup-python` | `v5` | Python 3.12 for pytest | Standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `databricks-sdk` | `>=0.102.0` | Python SDK (used in later phases) | Dependency in requirements.txt |
| `pytest` | `>=8.3.0` | Unit test runner | Phase 1 tests directory structure only; no substantive tests yet |
| `pytest-cov` | `>=6.0.0` | Coverage reporting | Required by CICD-01 (`--cov=src --cov-report=xml`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| OIDC federation | PAT token in GitHub Secrets | PAT leaks → entire workspace compromise; PAT rotation burden; OIDC is strictly superior |
| DABs schemas.yml | Terraform `databricks_schema` | Project decision locked: DABs only |
| Branch-scoped policy for dev | Environment-scoped for dev | Branch-scoped avoids requiring a GitHub Environment for dev, reducing friction on non-main branches |

**Installation (local dev):**
```bash
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
databricks auth login --host <workspace-url>
```

---

## Architecture Patterns

### Recommended Project Structure
```
dbx-mls/
├── databricks.yml              # Root bundle definition; include: references resources/
├── resources/
│   ├── schemas.yml             # UC lol_analytics catalog + bronze/silver/gold schemas
│   ├── clusters.yml            # Shared job cluster definition (DBR 16.4 LTS, Standard_F4s_v2)
│   └── jobs/
│       └── smoke_test_job.yml  # Smoke test job (permanent infrastructure health check)
├── notebooks/
│   └── smoke_test.py           # Databricks notebook: secrets + UC + table roundtrip
├── src/                        # Pipeline source (Phase 2+)
├── schemas/                    # Silver StructType definitions (Phase 3+)
├── tests/
│   └── unit/                   # pytest unit tests
├── docs/
│   ├── setup.md                # Lean reference guide for repo replication
│   └── posts/                  # LinkedIn deliverables (phase-1-article.md, phase-1-post.md)
├── .github/
│   └── workflows/
│       ├── ci.yml              # validate + pytest on every push
│       ├── cd-dev.yml          # deploy dev + run smoke test on push to main
│       └── cd-prod.yml         # deploy prod on v* tag (manual approval gate)
├── Makefile                    # make validate / make test / make smoke
├── requirements.txt            # Runtime dependencies
└── requirements-dev.txt        # Dev/test dependencies
```

### Pattern 1: `databricks.yml` Root Bundle
**What:** Central bundle file with `include:` directives pointing to resource YAMLs. Defines `dev` (default, development mode) and `prod` (production mode with explicit `root_path` and `run_as`).
**When to use:** Always — this is the single entry point for all bundle operations.
**Example:**
```yaml
# Source: https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/settings
bundle:
  name: dbx-mls
  databricks_cli_version: ">=0.250.0"

include:
  - resources/*.yml
  - resources/jobs/*.yml

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: ${var.databricks_host}

  prod:
    mode: production
    workspace:
      host: ${var.databricks_host}
      root_path: /Workspace/Shared/.bundle/dbx-mls/prod
    run_as:
      service_principal_name: ${var.sp_client_id}
```

### Pattern 2: Two OIDC Federation Policies (Branch-Scoped + Environment-Scoped)
**What:** The CI/dev deploy uses a branch-scoped federation policy (no `environment:` in the GitHub Actions job). The prod deploy uses an environment-scoped policy (requires `environment: prod` in the job block, which triggers GitHub Environment protection rules).
**When to use:** This split is the canonical pattern for dev/prod separation with OIDC and zero PAT tokens.
**Example (federation policy creation via Databricks CLI):**
```bash
# Source: https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-federation-policy
# Authenticate to account console first:
databricks auth login --host https://accounts.azuredatabricks.net --account-id ${ACCOUNT_ID}

# Dev policy — branch-scoped (no environment: key in workflow)
databricks account service-principal-federation-policy create ${SP_NUMERIC_ID} --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["https://github.com/<org>"],
    "subject": "repo:<org>/dbx-mls:ref:refs/heads/main"
  }
}'

# Prod policy — environment-scoped (job must have environment: prod)
databricks account service-principal-federation-policy create ${SP_NUMERIC_ID} --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["https://github.com/<org>"],
    "subject": "repo:<org>/dbx-mls:environment:prod"
  }
}'
```

### Pattern 3: GitHub Actions OIDC Workflow Structure
**What:** Three separate workflow files with the OIDC permission block and DATABRICKS_AUTH_TYPE set at job level.
**When to use:** All three workflows use this pattern — no PAT tokens anywhere.
**Example (ci.yml):**
```yaml
# Source: https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/provider-github
name: CI

on:
  push:
    branches: ["**"]

permissions:
  id-token: write   # REQUIRED for OIDC token issuance
  contents: read

jobs:
  validate-and-test:
    runs-on: ubuntu-latest
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - uses: databricks/setup-cli@v0.295.0
      - run: databricks bundle validate
      - run: pytest tests/unit/ --cov=src --cov-report=xml
```

**Example (cd-dev.yml — no `environment:` key):**
```yaml
name: CD Dev

on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy-dev:
    runs-on: ubuntu-latest
    # NO environment: key here — branch-scoped federation policy
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.ref }}  # avoids detached HEAD on tag events
      - uses: databricks/setup-cli@v0.295.0
      - run: databricks bundle deploy --target dev
      - run: databricks bundle run smoke_test_job --target dev
```

**Example (cd-prod.yml — environment-scoped):**
```yaml
name: CD Prod

on:
  push:
    tags: ["v*"]

permissions:
  id-token: write
  contents: read

jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: prod   # MUST match federation policy subject exactly (case-sensitive)
    concurrency:
      group: prod-deploy
      cancel-in-progress: false
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.ref }}
      - uses: databricks/setup-cli@v0.295.0
      - run: databricks bundle deploy --target prod
```

### Pattern 4: Schema Ownership Bootstrap
**What:** DABs creates schemas with the deploying identity as owner. Since the first deploy is always from CI (the SP), the SP automatically becomes schema owner. The workspace admin must grant the SP sufficient catalog-level privileges before the first deploy so the SP can actually create schemas.
**Critical sequence:**
1. Workspace admin grants SP `USE CATALOG` + `CREATE SCHEMA` on `lol_analytics`
2. GitHub Actions push triggers first `cd-dev.yml` deploy
3. SP creates `bronze`, `silver`, `gold` schemas — SP is automatically the owner
4. Admin verifies with `SHOW GRANTS ON SCHEMA lol_analytics.bronze`

**Ownership transfer (if schemas were pre-created by a human):**
```sql
-- Source: https://learn.microsoft.com/en-us/azure/databricks/data-governance/unity-catalog/manage-privileges/ownership
-- Run as workspace admin or current schema owner
ALTER SCHEMA lol_analytics.bronze OWNER TO `<sp-application-id>`;
ALTER SCHEMA lol_analytics.silver OWNER TO `<sp-application-id>`;
ALTER SCHEMA lol_analytics.gold   OWNER TO `<sp-application-id>`;
```

**Pre-deploy SP grants (run once by workspace admin):**
```sql
GRANT USE CATALOG  ON CATALOG lol_analytics                TO `<sp-application-id>`;
GRANT CREATE SCHEMA ON CATALOG lol_analytics               TO `<sp-application-id>`;
GRANT USE SCHEMA   ON SCHEMA lol_analytics.bronze          TO `<sp-application-id>`;
GRANT CREATE TABLE ON SCHEMA lol_analytics.bronze          TO `<sp-application-id>`;
GRANT MODIFY       ON SCHEMA lol_analytics.bronze          TO `<sp-application-id>`;
-- Repeat for silver and gold
```

### Pattern 5: Databricks Secrets CLI
**What:** Create a secret scope and store the Riot API key. Grant the SP `READ` permission (not `CAN_READ` — the CLI uses `READ`).
```bash
# Source: https://learn.microsoft.com/en-us/azure/databricks/security/secrets/
databricks secrets create-scope lol-pipeline
databricks secrets put-secret lol-pipeline riot-api-key --string-value "${RIOT_API_KEY}"
databricks secrets put-acl lol-pipeline "<sp-application-id>" READ
```

### Anti-Patterns to Avoid
- **Running `bundle deploy` locally before CI is set up:** The first deploy sets schema ownership. If a developer runs it locally, the human user becomes schema owner — not the SP. Extremely difficult to fix without dropping and recreating schemas.
- **Using `DATABRICKS_TOKEN` (PAT) anywhere in GitHub Secrets:** Violates CICD-04. Even as a "temporary fallback" this introduces a long-lived secret that can leak.
- **Using `@main` for `setup-cli` in prod workflow:** `@main` always pulls the latest version. Pin to `@v0.295.0` in `cd-prod.yml` for reproducibility.
- **Setting `environment:` key in the dev CD workflow job:** If the job has `environment: dev`, the branch-scoped federation policy won't match — it will try to match `environment:dev` in the subject claim.
- **Leaving `run_as` out of the `prod` target:** Without `run_as`, jobs run as the deploying identity. In prod, this should explicitly be the SP.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OIDC token exchange | Custom JWT exchange logic | `DATABRICKS_AUTH_TYPE: github-oidc` env var | Databricks CLI handles the full OIDC flow automatically; token refresh included |
| Bundle validation | Custom YAML parser or Databricks API calls | `databricks bundle validate` | Built-in; validates schema, resolves variables, checks workspace connectivity |
| Secret redaction in logs | Custom log scrubbing | `dbutils.secrets.get()` + Databricks auto-redaction | Databricks automatically redacts secret values in notebook and job logs |
| Schema grants SQL script runner | Python wrapper around Databricks API | SQL notebook or CLI one-time script documented in `docs/setup.md` | Admin one-time action; complexity not justified |
| Job concurrency protection | Workflow-level locks or mutex | GitHub Actions `concurrency:` group | Native feature; `cancel-in-progress: false` prevents prod race conditions |

**Key insight:** Every infrastructure primitive needed in this phase (auth, deploy, secrets, schema management) has a first-party tool. The entire phase is configuration work, not code work.

---

## Common Pitfalls

### Pitfall 1: OIDC Subject Claim Case-Sensitivity
**What goes wrong:** Federation policy has `environment:prod` but the workflow job has `environment: Prod` (capital P). Authentication silently fails with a 401 — no hint that the subject claim is the cause.
**Why it happens:** GitHub Actions preserves the exact case of the `environment:` value in the JWT subject claim. Databricks performs a case-sensitive string match against the policy subject.
**How to avoid:** Copy the exact environment name from the GitHub repository's Environments settings into both the federation policy subject and the workflow `environment:` key. Use lowercase `prod` consistently.
**Warning signs:** CI/CD fails at the first Databricks CLI step with `Error: authentication failed` or `403 Forbidden` with no further context.

### Pitfall 2: First Deploy Must Be From CI (Schema Ownership Lock-In)
**What goes wrong:** Developer runs `databricks bundle deploy --target dev` locally while setting up the repo. Human user becomes schema owner. Later, the CI SP cannot modify schemas it doesn't own.
**Why it happens:** DABs schema resources are owned by the deploying identity. DABs does not support transferring schema ownership or setting a different owner via `run_as` — the `run_as` field is explicitly ignored for schema operations.
**How to avoid:** Gate `databricks.yml` commit behind Plan 01-02 completion. Document in `docs/setup.md` with a bold warning. The Makefile `smoke` target should only run after CI is proven working.
**Warning signs:** `SHOW GRANTS ON SCHEMA lol_analytics.bronze` shows a user email instead of an SP application ID.

### Pitfall 3: `environment:` Key in Dev CD Workflow
**What goes wrong:** Adding `environment: dev` to the `cd-dev.yml` job block (thinking it "scopes" the deployment to dev) causes the OIDC token subject to become `repo:<org>/dbx-mls:environment:dev`. The branch-scoped federation policy (`...ref:refs/heads/main`) no longer matches.
**Why it happens:** The `environment:` key in a GitHub Actions job changes the OIDC token subject from branch-scoped to environment-scoped. It also requires a GitHub Environment named `dev` to exist.
**How to avoid:** The dev CD workflow job must NOT have an `environment:` key. Only `cd-prod.yml` uses `environment: prod`.
**Warning signs:** Dev deploy fails after OIDC was working; error is authentication-related.

### Pitfall 4: `setup-cli@main` Version Drift in Prod
**What goes wrong:** `databricks/setup-cli@main` in `cd-prod.yml` installs whatever the latest CLI version is at run time. A new CLI version with breaking changes causes prod deploys to fail unexpectedly.
**Why it happens:** `@main` is a mutable reference; the action installer always fetches the current main branch.
**How to avoid:** Pin `cd-prod.yml` to `databricks/setup-cli@v0.295.0` (specific immutable tag). `ci.yml` and `cd-dev.yml` can use `@main` if preferred, but prod must be pinned.
**Warning signs:** Prod deploy breaks without any code changes after a Databricks CLI release.

### Pitfall 5: `autotermination_minutes` on Job Clusters
**What goes wrong:** Setting `autotermination_minutes: 120` (or any non-zero value) on a job cluster causes a validation warning or unexpected behavior because job clusters terminate when the job finishes — auto-termination is not applicable.
**Why it happens:** Developers copy interactive cluster config patterns to job clusters.
**How to avoid:** Set `autotermination_minutes: 0` (D-02 decision). This is the correct value for job clusters.
**Warning signs:** `databricks bundle validate` emits a warning about auto-termination on job clusters.

### Pitfall 6: GitHub Repo Variables vs Secrets for Non-Secret Values
**What goes wrong:** `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID` stored as GitHub Secrets are masked in logs, making debugging difficult when the workspace URL or client ID is wrong.
**Why it happens:** Developers default to using Secrets for all sensitive-looking values.
**How to avoid:** Store `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID` as GitHub repository **Variables** (not Secrets). These are not sensitive values — the workspace URL is public and the client ID is a UUID that grants no access without the OIDC token. Only PAT tokens or OAuth secrets need GitHub Secrets.
**Warning signs:** Debugging CI auth failures is impossible because the host URL is masked.

---

## Code Examples

### DBR 16.4 LTS Cluster Config (resources/clusters.yml)
```yaml
# Source: https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/16.4lts
# spark_version verified: DBR 16.4 LTS = Apache Spark 3.5.2, Python 3.12
resources:
  clusters:
    job_cluster:
      cluster_name: dbx-mls-job-cluster
      spark_version: 16.4.x-scala2.12
      node_type_id: Standard_F4s_v2
      autotermination_minutes: 0
      spark_conf:
        spark.databricks.cluster.profile: singleUser
      num_workers: 0
      spark_conf:
        spark.master: local[*, 4]
```

### Smoke Test Notebook (notebooks/smoke_test.py)
```python
# Databricks notebook source
# COMMAND ----------
# Test 1: Riot API key retrievable (value auto-redacted in logs by Databricks)
api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
assert len(api_key) > 0, "Riot API key is empty"
print("Test 1 PASSED: API key retrieved (value redacted)")

# COMMAND ----------
# Test 2: Unity Catalog access
schemas = spark.sql("SHOW SCHEMAS IN lol_analytics").collect()
schema_names = [row[0] for row in schemas]
assert "bronze" in schema_names, f"bronze schema not found. Got: {schema_names}"
print(f"Test 2 PASSED: UC schemas visible: {schema_names}")

# COMMAND ----------
# Test 3: Bronze table roundtrip
spark.sql("CREATE TABLE IF NOT EXISTS lol_analytics.bronze.smoke_test (id INT, ts TIMESTAMP) USING DELTA")
spark.sql("INSERT INTO lol_analytics.bronze.smoke_test VALUES (1, current_timestamp())")
count = spark.sql("SELECT COUNT(*) as cnt FROM lol_analytics.bronze.smoke_test").collect()[0]["cnt"]
assert count >= 1, "Smoke test table write/read failed"
spark.sql("DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test")
print("Test 3 PASSED: Bronze table roundtrip successful")

# COMMAND ----------
print("SMOKE TEST PASSED")
```

### Smoke Test Job (resources/jobs/smoke_test_job.yml)
```yaml
resources:
  jobs:
    smoke_test_job:
      name: dbx-mls-smoke-test
      job_clusters:
        - job_cluster_key: smoke_cluster
          new_cluster:
            spark_version: 16.4.x-scala2.12
            node_type_id: Standard_F4s_v2
            num_workers: 0
            autotermination_minutes: 0
            spark_conf:
              spark.databricks.cluster.profile: singleUser
              spark.master: "local[*, 4]"
      tasks:
        - task_key: smoke_test
          job_cluster_key: smoke_cluster
          notebook_task:
            notebook_path: ./notebooks/smoke_test.py
            source: WORKSPACE
```

### Databricks Secrets CLI Commands
```bash
# Source: https://learn.microsoft.com/en-us/azure/databricks/security/secrets/
# Ensure authenticated: databricks auth login --host <workspace-url>
databricks secrets create-scope lol-pipeline
databricks secrets put-secret lol-pipeline riot-api-key --string-value "${RIOT_API_KEY}"
# Grant SP READ access (permission value is READ, not CAN_READ)
databricks secrets put-acl lol-pipeline "<sp-application-id>" READ
# Verify
databricks secrets list-secrets lol-pipeline
databricks secrets get-acl lol-pipeline "<sp-application-id>"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PAT tokens in GitHub Secrets | OIDC Workload Identity (`DATABRICKS_AUTH_TYPE: github-oidc`) | 2023 (Databricks SDK) | No long-lived secrets; automatic token refresh |
| `DATABRICKS_BUNDLE_ENV` env var | `--target dev` / `--target prod` flag | CLI 0.200+ | Explicit; easier to audit |
| `databricks/setup-cli@v0.9.0` | `databricks/setup-cli@v0.295.0` | Continuous release | Pin to latest stable; 0.295.0 is current as of 2026-04-07 |
| PAT-based `run_as` | SP UUID in `run_as.service_principal_name` | DABs GA | Clean audit trail; no token rotation |

**Deprecated/outdated:**
- `DATABRICKS_TOKEN` GitHub Secret for CI/CD: replaced by OIDC; avoid entirely in new repos
- Legacy Databricks CLI (Python `databricks-cli` package): replaced by Go-based CLI 0.x; do not install via `pip install databricks-cli`

---

## Open Questions

1. **DBR 16.4 LTS exact `spark_version` string for single-node config**
   - What we know: DBR 16.4 LTS = Spark 3.5.2; two variants: `16.4.x-scala2.12` and `16.4.x-scala2.13`
   - What's unclear: For a `local[*]` single-node job cluster, whether `num_workers: 0` + `spark.master: local[*, 4]` or `single_node_cluster` flag is the correct pattern for Azure specifically
   - Recommendation: Use `num_workers: 0` + `spark.databricks.cluster.profile: singleUser` + `spark.master: "local[*, 4]"` per Roadmap D-03 decision. If `databricks bundle validate` rejects this, fall back to `num_workers: 1`.

2. **Unity Catalog `lol_analytics` catalog — pre-existing vs SP-created**
   - What we know: `resources/schemas.yml` can declare schemas under an existing catalog; it cannot create the catalog itself unless the SP has `CREATE CATALOG` on the metastore
   - What's unclear: Whether the workspace admin pre-creates `lol_analytics` catalog or if the SP creates it; the Roadmap says "catalog created" in INFRA-02 but doesn't specify by whom
   - Recommendation: Document in `docs/setup.md` that the workspace admin must create the `lol_analytics` catalog before the first CI deploy. The SP creates and owns the schemas. `resources/schemas.yml` references the existing catalog.

3. **`databricks bundle run` timeout behavior**
   - What we know: `databricks bundle run smoke_test_job --target dev` blocks until the job completes
   - What's unclear: Whether there is a default GitHub Actions step timeout that could kill the smoke test run before Databricks reports completion (GitHub's default is 6 hours per job; the smoke test should complete in under 5 minutes)
   - Recommendation: No action needed for Phase 1 smoke test. For Phase 2 long-running jobs, will need `timeout_seconds: 14400` in the job definition (already documented in STATE.md).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | pytest, requirements-dev.txt | Yes | 3.12.3 | — |
| Databricks CLI | Bundle validate, deploy, secrets | No | — | Install via `install.sh` (Plan 01-01) |
| Java 11 | PySpark local tests (Phase 2+) | No | — | Not needed for Phase 1 (no PySpark tests yet); install in Phase 2 |
| `make` | Makefile targets | Yes | GNU Make 4.3 | — |
| `git` | Repo operations | Yes | 2.43.0 | — |
| `gh` (GitHub CLI) | GitHub Environment creation | Yes | 2.83.2 | Manual via GitHub UI |
| pip | Python package install | No (pip3 not found) | — | Use `python3 -m pip` |

**Missing dependencies with no fallback:**
- Databricks CLI: must be installed in Plan 01-01. Use `curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh`

**Missing dependencies with fallback:**
- Java 11: not needed for Phase 1. Phase 2 plan must include Java 11 install (`sudo apt-get install openjdk-11-jdk`).
- pip: use `python3 -m pip install` instead of `pip3`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.3.0 |
| Config file | none in Phase 1 — created in Wave 0 |
| Quick run command | `pytest tests/unit/ -x -q` |
| Full suite command | `pytest tests/unit/ --cov=src --cov-report=xml` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Workspace exists with UC enabled | manual-only | — (prerequisite check; documented in setup.md) | N/A |
| INFRA-02 | `lol_analytics` catalog with 3 schemas exist | smoke (DAB job) | `databricks bundle run smoke_test_job --target dev` | Wave 0: `notebooks/smoke_test.py` |
| INFRA-03 | SP owns all three schemas | manual SQL | `SHOW GRANTS ON SCHEMA lol_analytics.bronze` | N/A |
| INFRA-04 | `databricks.yml` validates with DBR 16.4 | validate | `databricks bundle validate` | Wave 0: `databricks.yml` |
| INFRA-05 | Secret retrievable in notebook | smoke (DAB job) | `databricks bundle run smoke_test_job --target dev` | Wave 0: `notebooks/smoke_test.py` |
| INFRA-06 | Smoke test completes end-to-end | e2e (CI-triggered) | push to `main` → observe GitHub Actions | Wave 0: `notebooks/smoke_test.py`, `resources/jobs/smoke_test_job.yml` |
| INFRA-07 | `.gitignore` excludes secrets | manual | `git status --short` (must show 0 untracked creds) | Wave 0: `.gitignore` |
| CICD-01 | CI green on every push | e2e (CI) | push to any branch → observe `ci.yml` | Wave 0: `.github/workflows/ci.yml` |
| CICD-02 | Dev deploy on push to `main` | e2e (CI) | push to `main` → observe `cd-dev.yml` | Wave 0: `.github/workflows/cd-dev.yml` |
| CICD-03 | Prod deploy on `v*` tag with approval | e2e (CI) | tag `v0.1.0` → observe `cd-prod.yml` + approve | Wave 0: `.github/workflows/cd-prod.yml` |
| CICD-04 | Zero PAT tokens in GitHub Secrets | manual | inspect GitHub repo Settings → Secrets | N/A |
| CICD-05 | CLI pinned `>=0.250.0` | validate | `databricks --version` in CI logs | Wave 0: workflows |
| CICD-06 | No parallel prod deploys | manual | trigger two simultaneous prod tags; second must queue | Wave 0: `cd-prod.yml` `concurrency:` block |

### Sampling Rate
- **Per task commit:** `databricks bundle validate` (fast; ~5 seconds)
- **Per wave merge:** `databricks bundle validate` + `pytest tests/unit/ -x -q`
- **Phase gate:** All GitHub Actions workflows green + `SHOW GRANTS` SQL confirms SP ownership + `databricks secrets list-secrets lol-pipeline` shows `riot-api-key`

### Wave 0 Gaps (files that must exist before any other plan can proceed)
- [ ] `databricks.yml` — root bundle; Plan 01-01 delivers this
- [ ] `resources/schemas.yml` — UC schema declarations; Plan 01-03 delivers this
- [ ] `resources/clusters.yml` — shared cluster definition; Plan 01-01 delivers this
- [ ] `resources/jobs/smoke_test_job.yml` — smoke test job; Plan 01-04 delivers this
- [ ] `notebooks/smoke_test.py` — smoke test notebook; Plan 01-04 delivers this
- [ ] `.github/workflows/ci.yml` — Plan 01-02 delivers this
- [ ] `.github/workflows/cd-dev.yml` — Plan 01-02 delivers this
- [ ] `.github/workflows/cd-prod.yml` — Plan 01-02 delivers this
- [ ] `tests/unit/.gitkeep` — directory must exist for `pytest tests/unit/` to not fail; Plan 01-01 delivers this
- [ ] `pytest.ini` or `pyproject.toml` `[tool.pytest.ini_options]` — needed for `pytest --cov=src` to resolve correctly

---

## Project Constraints (from CLAUDE.md)

No `CLAUDE.md` found in the repository root. No project-specific directives to enforce beyond those in CONTEXT.md.

---

## Sources

### Primary (HIGH confidence)
- [Enable workload identity federation for GitHub Actions — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/provider-github) — OIDC federation setup steps, env vars, workflow YAML
- [Configure a federation policy — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-federation-policy) — Federation policy CLI commands, subject claim formats, case-sensitivity behavior
- [GitHub Actions — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/ci-cd/github) — Official CI/CD workflow examples, setup-cli action usage
- [Manage Unity Catalog object ownership — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/data-governance/unity-catalog/manage-privileges/ownership) — `ALTER SCHEMA ... OWNER TO` syntax, transfer permissions required
- [Databricks Runtime 16.4 LTS — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/16.4lts) — Confirmed: Spark 3.5.2, Python 3.12, released May 2025; `spark_version: 16.4.x-scala2.12`
- [Secret management — Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/security/secrets/) — Secret scope creation, `put-acl` with `READ` (not `CAN_READ`)
- [databricks/setup-cli — GitHub](https://github.com/databricks/setup-cli) — Version pinning: `@v0.295.0` or `@main with: version: 0.295.0`

### Secondary (MEDIUM confidence)
- [Databricks Asset Bundles resources — Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/resources) — Schema resource structure, `grants` field; owner limitation (deploying identity is always owner) confirmed by multiple community sources
- [Databricks CLI releases — GitHub](https://github.com/databricks/cli/releases) — Latest release v0.295.0 confirmed via GitHub API

### Tertiary (LOW confidence — flag for validation)
- Community sources (Databricks forums) corroborating that `run_as` is ignored for schema resources: verified indirectly via official docs statement that "owner of a schema resource is always the deployment user"

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against official docs and GitHub releases
- Architecture patterns: HIGH — all patterns derived from official Microsoft Learn docs
- OIDC federation: HIGH — official docs with exact CLI commands
- Schema ownership bootstrap: HIGH — official ownership docs + community corroboration
- Pitfalls: HIGH — all pitfalls derived from official doc warnings and explicit project constraints in STATE.md
- DBR spark_version string: MEDIUM — confirmed `16.4.x-scala2.12` from SDK issue references; the exact string for a `local[*]` single-node cluster should be validated with `databricks bundle validate`

**Research date:** 2026-04-07
**Valid until:** 2026-07-07 (90 days — DABs schema API changes infrequently; OIDC pattern is stable)
