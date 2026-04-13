---
phase: 2
slug: bronze-ingestion-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` or `pyproject.toml` (Wave 0 creates if missing) |
| **Quick run command** | `pytest tests/unit/ -x -q` |
| **Full suite command** | `pytest tests/unit/ --cov=src --cov-report=term-missing` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x -q`
- **After every plan wave:** Run `pytest tests/unit/ --cov=src --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | BRZ-01 | unit | `pytest tests/unit/test_riot_client.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | BRZ-01 | unit | `pytest tests/unit/test_riot_client.py::test_rate_limiter -x -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | BRZ-01 | unit | `pytest tests/unit/test_riot_client.py::test_429_handling -x -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | BRZ-02,BRZ-03 | unit | `pytest tests/unit/test_config.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | BRZ-04,BRZ-05,BRZ-06 | integration | manual SQL count verify | n/a | ⬜ pending |
| 02-04-01 | 04 | 3 | BRZ-07,BRZ-08,BRZ-09 | integration | manual SQL count verify | n/a | ⬜ pending |
| 02-05-01 | 05 | 4 | TEST-02,TEST-04 | unit+ci | `pytest tests/unit/ --cov=src` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/unit/__init__.py` — package marker
- [ ] `tests/unit/test_riot_client.py` — stubs for BRZ-01 (rate limiter, 429 handling, routing)
- [ ] `tests/unit/test_config.py` — stubs for BRZ-02/BRZ-03 (routing map, widget params)
- [ ] `tests/conftest.py` — shared fixtures (mock dbutils, mock requests)
- [ ] `src/__init__.py` — required for `import src.riot_client` in pytest and DAB GIT-source tasks
- [ ] `src/ingestion/__init__.py` — package marker for ingestion modules
- [ ] `src/common/__init__.py` — package marker for common utilities
- [ ] Java 11 install verification: `java -version 2>&1 | grep '11\.'`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `bronze.match_raw` populated with real KR data | BRZ-04,BRZ-06 | Requires live Riot API key and Databricks cluster | Run DAB job with `region=KR, tier=CHALLENGER`; check `SELECT COUNT(*) FROM lol_analytics.bronze.match_raw` |
| MERGE idempotency on second run | BRZ-06 | Requires real Delta table state | Run same DAB job twice; verify row count unchanged |
| Timeline task failure isolation | BRZ-07 | Requires intentional failure injection in DAB | Set invalid match ID; confirm summoner/account tasks still succeed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
