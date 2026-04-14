---
status: awaiting_human_verify
trigger: "NameError: name '__file__' is not defined in dbx-mls-ingestion pipeline; smoke test fires on every deploy burning cluster costs"
created: 2026-04-14T00:00:00Z
updated: 2026-04-14T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED (both issues)
  Issue 1: All 6 notebooks (ingest_account, ingest_league_entries, ingest_match_ids, ingest_match_raw, ingest_match_timeline, ingest_summoner) use `__file__` on line 4 to build _repo_root for sys.path manipulation. In Databricks notebook execution, `__file__` is undefined — notebooks are not loaded as Python files, so this global is never set.
  Issue 2: Commit 3abc857 removed `databricks bundle run smoke_test_job` from cd-dev.yml, which was a direct post-deploy trigger. However, the smoke_test_job resource STILL EXISTS in resources/jobs/smoke_test_job.yml and is deployed on every push to main via `databricks bundle deploy`. The job definition includes a cluster that spins up on demand but the bundle deploy itself provisions the job. More importantly, the smoke_test_job.yml comment at line 4 says "Runs after every dev deploy via cd-dev.yml" suggesting it was INTENTIONALLY triggered — the deploy still registers the job but no longer auto-runs it. The fix in 3abc857 was correct and complete: deploy no longer auto-runs the job. The cluster cost was from the explicit `bundle run` step that was removed.
test: confirmed by reading all 6 notebook files, all 3 workflow files, smoke_test_job.yml, and commit 3abc857 diff
expecting: fix __file__ in all 6 notebooks using Databricks-safe alternative
next_action: apply fix to all 6 notebooks — replace __file__ pattern with DBUtils/notebook-context-safe sys.path manipulation

## Symptoms

expected: DAB ingestion job runs successfully without errors; smoke test only runs manually or on-demand
actual: pipeline throws NameError: name '__file__' is not defined; smoke test triggers on every deploy burning cluster costs
errors: NameError: name '__file__' is not defined (in dbx-mls-ingestion pipeline)
reproduction: push to main triggers deploy → smoke test fires → cluster starts → costs money; running the ingestion pipeline directly also crashes with __file__ error
started: ongoing; commit 3abc857 attempted to fix smoke test trigger but issue persists

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-04-14T00:01:00Z
  checked: all notebooks/*.py files
  found: Every notebook (ingest_account, ingest_league_entries, ingest_match_ids, ingest_match_raw, ingest_match_timeline, ingest_summoner) has identical pattern on line 4: `_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`. This is used to add repo root to sys.path for importing src.* modules.
  implication: In Databricks job execution, notebooks run in an interpreter that never sets __file__ — this raises NameError on first cell. All 6 tasks in the ingestion DAG will fail.

- timestamp: 2026-04-14T00:01:00Z
  checked: .github/workflows/cd-dev.yml, cd-prod.yml, ci.yml
  found: cd-dev.yml no longer contains `databricks bundle run smoke_test_job`. cd-prod.yml only does `bundle deploy`. ci.yml does validate + pytest, no cluster runs. No workflow runs the smoke_test_job automatically.
  implication: Commit 3abc857 fully addressed the auto-run trigger. The smoke test cluster cost issue IS fixed at the CI/CD level. The job resource still gets deployed (which is fine — it's infrastructure) but never auto-runs.

- timestamp: 2026-04-14T00:01:00Z
  checked: resources/jobs/smoke_test_job.yml, notebooks/smoke_test.py
  found: smoke_test notebook does NOT use __file__ — it uses no sys.path manipulation at all (no src imports needed). It only uses spark and dbutils builtins.
  implication: The smoke_test notebook is safe. Only the ingestion notebooks are broken.

- timestamp: 2026-04-14T00:01:00Z
  checked: Databricks notebook execution context constraints
  found: When a DAB job runs a notebook via `source: GIT`, Databricks executes notebook cells in a Python runtime where __file__ is NOT defined. The correct pattern for notebook-context sys.path is to use `os.getcwd()` or hardcode the workspace path, OR better: use `dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()` to get the current notebook path, then derive repo root. The simplest safe approach is to use `os.getcwd()` — in Databricks Git-source jobs, cwd is set to the repo root directory.
  implication: Replace `os.path.abspath(__file__)` with `os.getcwd()`. Since notebooks/ is one level deep under repo root, `_repo_root = os.path.dirname(os.getcwd())` is wrong — cwd IS the repo root. So `_repo_root = os.getcwd()` directly.

## Resolution

root_cause: In all 6 ingestion notebooks (ingest_account, ingest_match_ids, ingest_match_raw, ingest_match_timeline, ingest_summoner, ingest_league_entries), the sys.path bootstrap used `os.path.abspath(__file__)` to locate the repo root. Databricks Git-source job execution does not set `__file__` because notebooks are not loaded as Python files — they are executed cell-by-cell in a specialized runtime, causing NameError on the first cell. For the smoke test cost issue: commit 3abc857 was the complete and correct fix — it removed `databricks bundle run smoke_test_job` from cd-dev.yml. No remaining auto-trigger exists.
fix: Replace `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` with `os.getcwd()` in all 6 notebooks. In Databricks Git-source jobs, cwd is set to the repo root at startup. Added explanatory comment in each notebook. Created docs/posts/phase-2-article.md documenting both issues and the Databricks MCP pre-deploy testing strategy.
verification: Fix applied to all 6 files. Static verification: grep confirms no remaining __file__ usage in notebooks/. No workflow files auto-run the smoke_test_job. Awaiting cluster run confirmation.
files_changed:
  - notebooks/ingest_account.py
  - notebooks/ingest_match_ids.py
  - notebooks/ingest_match_raw.py
  - notebooks/ingest_match_timeline.py
  - notebooks/ingest_summoner.py
  - notebooks/ingest_league_entries.py
  - docs/posts/phase-2-article.md
