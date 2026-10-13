# Runbook

Operational procedures. Written to be followed by someone who did not build the platform.

## First-time setup

### 1. Local tooling

```bash
uv sync                                  # Python 3.12, project dependencies
uv run pre-commit install                # ruff, secret scanning, trailing whitespace
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
databricks version
```

### 2. Authenticate to the workspace

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com
databricks current-user me               # confirms the connection
```

### 3. Create secrets

```bash
databricks secrets create-scope mls
databricks secrets put-secret mls riot_api_key        # from developer.riotgames.com
databricks secrets put-secret mls pseudonym_salt      # generate once; see the warning below
```

!!! danger "The pseudonymization salt is permanent"
    `pseudonym_salt` must never change. Rotating it changes every `player_sk`, which silently
    breaks every join of a player across matches and across ladder snapshots. Generate it
    once with `openssl rand -hex 32`, store it in the secret scope, and keep an offline copy
    somewhere safe. If it is lost, historical player-level continuity is unrecoverable.

### 4. Deploy

```bash
databricks bundle validate -t prod
databricks bundle deploy  -t prod        # creates catalogs, schemas, volumes, jobs, pipeline
```

### 5. Verify

```bash
databricks bundle run ingest_and_transform_challenger -t dev   # minimum scope
```

## Daily development loop

```bash
git switch -c feat/<issue>-<slug>
# edit
uv run ruff check . && uv run ruff format .
uv run pytest
databricks bundle deploy -t dev          # dev target; schedules stay paused
databricks bundle run ingest_and_transform_challenger -t dev
# commit via the /commit skill, open the PR via the /open-pr skill
```

Never create a job, pipeline, schema or volume through the workspace UI. Anything not in the
bundle is outside the system of record and will be overwritten or orphaned on the next
deploy.

## Renewing the Riot API key

The development key expires every 24 hours.

```bash
# 1. regenerate at https://developer.riotgames.com (instant, requires a Riot account)
databricks secrets put-secret mls riot_api_key
# 2. re-run if a scheduled run was skipped
databricks bundle run ingest_and_transform_challenger -t prod
```

A run that finds an invalid key exits as **SKIPPED**, not failed: it logs the reason and does
no work. A skipped run in the history is expected behaviour, not an incident.

If a personal key has been approved by Riot, it does not expire and this procedure becomes
unnecessary — update the secret once.

## Interpreting a run

| Symptom | Meaning | Action |
|---|---|---|
| task log ends with `SKIPPED: Riot API key expired` | credential not valid at run time | renew the key and re-run |
| many `429 rate limited, backing off` lines | normal under sustained fetching | none; the client handles it |
| `RetriesExhausted` | Riot API degraded or unreachable | re-run later; check Riot status |
| pipeline fails on a structural expectation | parsing is wrong, not the data | fix the transform; do not relax the expectation |
| `drop_rate` spike in `ops.dq_metrics` | upstream payload changed, or a transform is wrong | inspect the affected rows in bronze |
| run produced far fewer matches than usual | ladder smaller, or many matches already landed | compare against the landing-zone file count |

## Inspecting a dropped record

Dropped records are not kept in a quarantine table. They remain in bronze in their original
form.

```sql
SELECT payload:info.participants
FROM mls.bronze.riot_matches
WHERE match_id = 'KR_7891234567';
```

## Recovering from account loss

Free Edition accounts may be deleted after inactivity. Full recovery:

1. Create a new Free Edition workspace.
2. `databricks auth login` against the new host; update `databricks.yml` if the host changed.
3. Re-create the secret scope, including the **original** `pseudonym_salt` from the offline
   copy.
4. `databricks bundle deploy -t prod`.
5. Re-run ingestion. Historical data is not recoverable unless an export exists outside
   Databricks.

This is why the repository must reconstruct every resource, and why the salt is kept offline.

## Rotating the Databricks token

```bash
# 1. create a new PAT in the workspace UI
gh secret set DATABRICKS_TOKEN            # update the GitHub Actions secret
databricks auth login                     # update the local profile
# 2. revoke the old token in the workspace UI
```

## Maintenance job

`maintain_storage` runs daily and performs `OPTIMIZE`, `VACUUM`, landing-zone retention and
freshness measurement. Its failure notification matters more than its output: it is also what
keeps the account active. If it has been failing for several days, treat it as urgent.
