# Phase 1: Building a Production Azure Databricks Lakehouse Foundation — OIDC, DABs, and Unity Catalog

Most Databricks tutorials skip the hard part. They provision a workspace, hardcode a PAT token, and call it CI/CD. What I built in Phase 1 of dbx-mls is what enterprise data engineering actually looks like: OIDC Workload Identity Federation so no token ever touches a GitHub repository variable, Databricks Asset Bundles as infrastructure-as-code, Unity Catalog with schema ownership assigned from CI — not from a developer's laptop — and a permanent smoke test that runs on every deploy to prove the infrastructure is healthy.

This is a portfolio project targeting Azure Databricks senior DE roles. The stack is intentional: Azure because that is where enterprise Databricks workloads live, Unity Catalog because hiring managers now expect it, DABs because they are the native Databricks IaC primitive that maps cleanly to DE workflows rather than platform engineering ones. The goal is a pipeline a recruiter can run end-to-end in under 30 minutes and recognize as production-grade — not a tutorial skeleton.

Phase 1 covers the full foundation: no ingestion code, no Bronze or Silver tables yet. Just the scaffolding that every subsequent phase depends on. This article walks through the four key decisions in that foundation.

---

## The Architecture Decision: OIDC over PATs

PATs (Personal Access Tokens) are the standard Databricks CI/CD starting point and a security liability. They are long-lived credentials that must be rotated manually, stored as GitHub secrets, and scoped to an individual user — meaning they expire with that user's employment. When someone's PAT leaks through a log line, you have a workspace-wide incident.

OIDC Workload Identity Federation eliminates the credential entirely. GitHub Actions requests a short-lived OIDC token from GitHub's identity provider at runtime. That token is passed to `azure/login@v2`, which authenticates to Azure AD and receives an Azure access token for the Service Principal. The Databricks CLI then uses `DATABRICKS_AUTH_TYPE: azure-cli` to obtain workspace access via Azure AD — not directly via a Databricks token endpoint. No credential is stored anywhere. No rotation burden. No secret to leak.

The trust relationship that makes this possible is configured as Federated Identity Credentials on the App Registration in Azure AD — not as Databricks Account Console CLI commands. Two credentials are created (via Azure portal or `az ad app federated-credential create`):

```bash
# Dev credential — branch-scoped, trusts any run from the main branch
az ad app federated-credential create --id <app-object-id> --parameters '{
  "name": "github-dev",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<org>/dbx-mls:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

# Prod credential — environment-scoped, requires GitHub Environment approval gate
az ad app federated-credential create --id <app-object-id> --parameters '{
  "name": "github-prod",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<org>/dbx-mls:environment:prod",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

Two separate Federated Identity Credentials serve two different trust boundaries. The dev credential trusts any push to the `main` branch. The prod credential trusts only a job running in the `prod` GitHub Environment, which requires a human approval gate. The subject claim format is the key detail: `ref:refs/heads/main` for branch-scoped, `environment:prod` for environment-scoped — and this match is case-sensitive. A lowercase `prod` in the credential subject and an uppercase `Prod` in the GitHub Environment name produce a cryptic 401 with no useful error message.

GitHub Actions uses three repository-level variables — `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and `AZURE_TENANT_ID` — and no secrets. `DATABRICKS_CLIENT_ID` is the SP's Azure AD application UUID (used both by `azure/login` as the client ID and by the bundle as the `run_as` identity). `AZURE_TENANT_ID` is the Azure AD tenant UUID, required by `azure/login@v2`. `DATABRICKS_HOST` is the workspace URL. All three are non-sensitive (UUIDs and URLs) and safe in variables rather than secrets. The credentials exchange happens entirely within the Azure AD token flow.

---

## Databricks Asset Bundles — IaC for Jobs and Schemas

Databricks Asset Bundles (DABs) are the native IaC primitive for Databricks resources. Every job, cluster configuration, and schema is declared in YAML and deployed via `databricks bundle deploy`. No Terraform, no manual UI clicks that become out-of-sync with reality.

The root bundle file, `databricks.yml`, declares the project structure and targets:

```yaml
bundle:
  name: dbx-mls
  databricks_cli_version: ">=0.250.0"

include:
  - resources/jobs/*.yml
  - resources/schemas.yml

variables:
  sp_client_id:
    description: "Service Principal client ID (UUID) used for prod run_as"

permissions:
  - service_principal_name: ${var.sp_client_id}
    level: CAN_MANAGE

targets:
  dev:
    default: true
    workspace:
      root_path: /Workspace/Users/${var.sp_client_id}/.bundle/dbx-mls/dev

  prod:
    mode: production
    workspace:
      root_path: /Workspace/Shared/.bundle/dbx-mls/prod
    run_as:
      service_principal_name: ${var.sp_client_id}
```

The `include:` directives pull in job definitions and schema declarations explicitly — `resources/jobs/*.yml` picks up every job file added in future phases without touching the root bundle. The `permissions:` block grants the Service Principal `CAN_MANAGE` on the deployed bundle path; without it, the job cluster cannot read the deployed artifacts at runtime. The dev target has no `mode: development` — that flag was removed because it generates user-prefixed resource paths that the SP cannot access; instead, the dev target uses a fixed `root_path` scoped to the SP's workspace directory. The `run_as` block on the prod target ensures production jobs execute under the Service Principal's identity, not the deploying user — a hard governance requirement for audit compliance.

One hard-won lesson: `workspace.host` cannot be set in `databricks.yml` with variable interpolation in CLI v0.295.0. The CLI rejects it for authentication fields. The correct pattern is `DATABRICKS_HOST` as an environment variable, set in the GitHub Actions workflow env block, never in the bundle file itself.

---

## Unity Catalog Schema Ownership Bootstrap

Unity Catalog enforces a governance model that catches most teams off guard: the identity that creates a schema owns it. If a developer runs `databricks bundle deploy` from their laptop before the Service Principal does, the schemas are created under that developer's identity. The SP then cannot modify them — and fixing this without dropping and recreating the schemas is painful.

The correct bootstrap sequence: a workspace admin runs these SQL grants once, before any deploy, to give the SP the permissions it needs to create and own the schemas:

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

Then CI deploys, the SP creates the schemas, and ownership is correct from day one. Verify it worked:

```sql
SHOW GRANTS ON SCHEMA lol_analytics.bronze;
```

The output must show the SP application UUID as owner — not a human email. If a human email appears, the schema was created locally first and ownership must be corrected before any Phase 2 work begins.

The `resources/schemas.yml` DAB file declares the three schemas as managed resources so future deploys keep them in sync:

```yaml
resources:
  schemas:
    bronze:
      catalog_name: lol_analytics
      name: bronze
      comment: "Raw Riot API JSON responses — Bronze layer (dbx-mls)"
    silver:
      catalog_name: lol_analytics
      name: silver
      comment: "Schema-enforced typed Delta tables — Silver layer (dbx-mls)"
    gold:
      catalog_name: lol_analytics
      name: gold
      comment: "Analytics aggregations — Gold layer (dbx-mls)"
```

---

## GitHub Actions Pipeline — Three Workflow Files, Zero Secrets

Three workflows handle the full CI/CD lifecycle:

**`ci.yml`** — runs on every push to every branch. Validates the bundle, runs the unit test suite. The OIDC environment block:

```yaml
permissions:
  id-token: write   # REQUIRED for OIDC token issuance
  contents: read

jobs:
  validate-and-test:
    runs-on: ubuntu-latest
    env:
      DATABRICKS_AUTH_TYPE: azure-cli
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      BUNDLE_VAR_sp_client_id: ${{ vars.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.DATABRICKS_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          allow-no-subscriptions: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - uses: databricks/setup-cli@v0.295.0
      - run: databricks bundle validate
      - run: pytest tests/unit/ --cov=src --cov-report=xml
```

`permissions: id-token: write` is the line that enables OIDC token issuance. Without it, GitHub does not generate the token and `azure/login@v2` cannot authenticate. `azure/login@v2` exchanges the GitHub OIDC token for an Azure AD access token on behalf of the Service Principal. `DATABRICKS_AUTH_TYPE: azure-cli` tells the Databricks CLI to use the Azure CLI credential (set up by `azure/login`) rather than falling back to PAT lookup or a Databricks-native OIDC flow. `BUNDLE_VAR_sp_client_id` supplies the `sp_client_id` bundle variable required by the prod `run_as` block.

**`cd-dev.yml`** — runs on push to `main`. Deploys the dev target, then immediately runs the smoke test job. Also uses `azure/login@v2` + `DATABRICKS_AUTH_TYPE: azure-cli` and passes `BUNDLE_VAR_sp_client_id` and `AZURE_TENANT_ID` in env. No `environment:` key — without it, the GitHub OIDC token subject claim uses the `ref:refs/heads/main` format, which matches the dev Federated Identity Credential. If an `environment:` key were added here, the subject claim would switch to the environment format and the dev credential would reject it.

**`cd-prod.yml`** — runs on version tags. Also uses `azure/login@v2` + `DATABRICKS_AUTH_TYPE: azure-cli`. Uses `environment: prod` which triggers the GitHub Environment approval gate. The `concurrency` block prevents concurrent prod deploys:

```yaml
environment: prod   # MUST match Federated Identity Credential subject exactly — case-sensitive
concurrency:
  group: prod-deploy
  cancel-in-progress: false
```

`cancel-in-progress: false` is deliberate — a prod deploy in progress should never be cancelled by a newer push. The newer push queues behind it.

The branch-scoped vs environment-scoped split is the key architectural decision: dev CI/CD requires no human approval (branch scope), prod requires a human to click "Approve" in the GitHub UI (environment scope). Same Azure AD OIDC mechanism, different trust boundaries.

---

## The Smoke Test: Infrastructure Health on Every Deploy

The smoke test is a permanent fixture — it does not get removed when Phase 2 pipeline code is added. It runs after every dev deploy and answers one question: is the workspace healthy?

Three validations per D-06:

**Validation 1** — Riot API key retrievable from Databricks Secrets. Databricks automatically redacts the key value in all notebook and job logs, so only `[REDACTED]` appears:

```python
api_key = dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")
assert len(api_key) > 0, "riot-api-key returned an empty string — check secret value"
print("Validation 1 PASSED: Riot API key retrieved (value redacted in logs)")
```

**Validation 2** — Unity Catalog accessible from job cluster. Verifies the SP's grants are intact and all three schemas exist:

```python
schemas_df = spark.sql("SHOW SCHEMAS IN lol_analytics")
schema_names = [row["databaseName"] for row in schemas_df.collect()]
assert "bronze" in schema_names, f"bronze schema not found. Got: {schema_names}"
assert "silver" in schema_names, f"silver schema not found. Got: {schema_names}"
assert "gold" in schema_names, f"gold schema not found. Got: {schema_names}"
print(f"Validation 2 PASSED: UC schemas confirmed: {schema_names}")
```

**Validation 3** — Bronze table roundtrip. Creates a temporary Delta table, inserts a row, reads it back, drops the table. Confirms the SP can create, write, and drop tables in the bronze schema:

```python
spark.sql("DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test")
spark.sql("CREATE TABLE lol_analytics.bronze.smoke_test (id BIGINT, msg STRING) USING DELTA")
spark.sql("INSERT INTO lol_analytics.bronze.smoke_test VALUES (1, 'smoke')")
result = spark.sql("SELECT COUNT(*) as cnt FROM lol_analytics.bronze.smoke_test").collect()[0]["cnt"]
assert result >= 1, f"Expected at least 1 row, got {result}"
spark.sql("DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test")
print("Validation 3 PASSED: Bronze table roundtrip (create/read/drop) succeeded")
```

If any validation fails, the CI run fails and the phase transition to Phase 2 is blocked. This is the acceptance gate for Phase 1.

---

## How I Built This

I used Claude Code throughout Phase 1 as a scaffolding and documentation assistant. The YAML files, workflow templates, and this article were generated or refined with Claude's help. The architecture decisions — OIDC over PATs, the two Federated Identity Credentials strategy (branch-scoped dev, environment-scoped prod), the SP ownership bootstrap sequence, the permanent smoke test pattern, and the choice to use DABs over Terraform — are engineering decisions made by me based on enterprise DE experience and the hiring signal I want this portfolio to project.

Claude is good at remembering YAML syntax and generating boilerplate I would otherwise have to look up. It is not the reason this architecture is correct. That part requires knowing what "correct" looks like for production Databricks workloads.

---

## Lessons Learned and What Comes Next

Three things I would tell anyone setting up this stack for the first time:

1. **OIDC subject claim format is case-sensitive and unforgiving.** `environment:prod` and `environment:Prod` are different strings. The subject is set in the Azure AD Federated Identity Credential on the App Registration — a mismatch with the GitHub Environment name produces a silent 401 with no diagnostic message. Verify with `az ad app federated-credential list --id <app-object-id>` to confirm the credential subject matches the GitHub Environment name exactly before pushing to CI.

2. **SP schema ownership is set on first deploy, not first table creation.** The bootstrap SQL grants must run before CI touches the workspace. There is no undo that does not involve dropping schemas.

3. **`workspace.host` does not belong in `databricks.yml`.** The CLI rejects variable interpolation for authentication fields. Use the `DATABRICKS_HOST` environment variable in the workflow instead.

Phase 2 builds the Bronze ingestion layer on top of this foundation: Riot Games API ingestion, a dual-bucket rate limiter, and the first real Delta tables in `lol_analytics.bronze`. The smoke test job will continue running on every dev deploy, now joined by ingestion job definitions.

The full project is open source at `<github-repo-url>`. The `docs/setup.md` file covers the complete replication process for anyone who wants to run this in their own Azure subscription.
