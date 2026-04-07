---
phase: 1
slug: infrastructure-governance-ci-cd-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-07
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.3.0 |
| **Config file** | none — Wave 0 installs `pytest.ini` or `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/ -x -q` |
| **Full suite command** | `pytest tests/unit/ --cov=src --cov-report=xml` |
| **Estimated runtime** | ~5 seconds (unit only; e2e via GitHub Actions) |

---

## Sampling Rate

- **After every task commit:** Run `databricks bundle validate` (~5 seconds)
- **After every plan wave:** Run `databricks bundle validate` + `pytest tests/unit/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + all GitHub Actions workflows green + `SHOW GRANTS` SQL confirms SP ownership + `databricks secrets list-secrets lol-pipeline` shows `riot-api-key`
- **Max feedback latency:** 5 seconds (local validate); ~3 minutes (CI e2e)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01-01 | 1 | INFRA-01, INFRA-04, INFRA-07 | validate | `databricks bundle validate` | ❌ W0 | ⬜ pending |
| 1-02-01 | 01-02 | 2 | CICD-01, CICD-02, CICD-03, CICD-04, CICD-05, CICD-06 | e2e (CI) | push to `main` → observe GitHub Actions | ❌ W0 | ⬜ pending |
| 1-03-01 | 01-03 | 3 | INFRA-02, INFRA-03, INFRA-05 | smoke + manual SQL | `databricks bundle run smoke_test_job --target dev` + `SHOW GRANTS ON SCHEMA lol_analytics.bronze` | ❌ W0 | ⬜ pending |
| 1-04-01 | 01-04 | 4 | INFRA-06 | e2e (CI) | push to `main` → CI green → dev deploy → smoke job completes | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `databricks.yml` — root bundle definition (Plan 01-01 delivers)
- [ ] `resources/schemas.yml` — UC schema declarations (Plan 01-03 delivers)
- [ ] `resources/clusters.yml` — shared cluster definition (Plan 01-01 delivers)
- [ ] `resources/jobs/smoke_test_job.yml` — smoke test job (Plan 01-04 delivers)
- [ ] `notebooks/smoke_test.py` — smoke test notebook (Plan 01-04 delivers)
- [ ] `.github/workflows/ci.yml` — CI workflow (Plan 01-02 delivers)
- [ ] `.github/workflows/cd-dev.yml` — dev CD workflow (Plan 01-02 delivers)
- [ ] `.github/workflows/cd-prod.yml` — prod CD workflow (Plan 01-02 delivers)
- [ ] `tests/unit/.gitkeep` — directory must exist for `pytest tests/unit/` to not error (Plan 01-01 delivers)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — needed for `--cov=src` to resolve correctly (Plan 01-01 delivers)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Azure workspace exists with Unity Catalog enabled | INFRA-01 | Cloud prerequisite; cannot be automated in DABs | Check `databricks catalogs list` returns `lol_analytics`; document in `docs/setup.md` |
| SP is schema owner (not human user) | INFRA-03 | SQL DDL inspection | `SHOW GRANTS ON SCHEMA lol_analytics.bronze` — must show SP app-id, not human email |
| Zero PAT tokens in GitHub Secrets | CICD-04 | GitHub UI only | Inspect repo Settings → Secrets and variables → Actions — must be empty |
| No parallel prod deploys (concurrency block) | CICD-06 | Requires two simultaneous tag triggers | Trigger `v0.1.0` and `v0.1.1` tags rapidly; second must queue, not run concurrently |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (local validate) / ~3min (CI e2e)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
