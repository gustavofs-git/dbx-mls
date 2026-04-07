# Phase 1: Infrastructure, Governance & CI/CD Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 01-infrastructure-governance-ci-cd-foundation
**Areas discussed:** Dev cluster shape, Smoke test permanence, Setup doc depth, LinkedIn Phase 1 angle

---

## Dev Cluster Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Standard_DS3_v2 | 14 GB RAM, 4 vCPUs. Databricks default, maximum hiring signal recognizability. | |
| Standard_F4s_v2 | 8 GB RAM, 4 vCPUs. ~30% cheaper, faster cold start. Cost-optimization signal. | ✓ |
| Standard_DS4_v2 | 28 GB RAM, 8 vCPUs. Overkill for Phase 1 but headroom for later phases. | |
| You decide | Leave cluster selection to Claude. | |

**User's choice:** Standard_F4s_v2

**Notes:** User explicitly prioritized cost minimization. The portfolio needs to be buildable cheaply — Standard_F4s_v2 is the deliberate trade-off between enterprise recognizability and running cost.

| Option | Description | Selected |
|--------|-------------|----------|
| Same type as dev | Prod/dev parity at the config level. | ✓ |
| Larger for prod | E.g. Standard_DS4_v2 for prod. Demonstrates right-sizing. | |
| You decide | Claude picks. | |

**User's choice:** Same type as dev — keeps it simple.

---

## Smoke Test Permanence

| Option | Description | Selected |
|--------|-------------|----------|
| Keep permanently | Stays in bundle as ongoing health-check job. | ✓ |
| Remove after Phase 1 | One-time validation only, cleaner bundle going forward. | |

**User's choice:** Keep permanently (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-trigger in cd-dev.yml | Every push to main: deploy → run smoke test → assert exit 0. | ✓ |
| Manual trigger only | Run via CLI or make target, not wired into CI. | |

**User's choice:** Auto-trigger in cd-dev.yml (Recommended)

---

## Setup Doc Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Lean reference checklist | Assumes existing workspace, commands and gotchas. Fast for hiring managers. | ✓ |
| Full tutorial | Step-by-step from blank Azure subscription. Longer, accessible to anyone. | |

**User's choice:** Lean reference (with important context below)

**Notes:** User provided key framing: the repo is a pattern demonstration, not a shared service. Reviewers cannot use the author's clusters — they must provision their own and bear the Azure costs. The author is cost-conscious and wants the docs to reflect that. "I am poor and want to build this as cheap as possible."

**Topics selected for coverage:** Riot API key rotation, GitHub OIDC federation setup, Unity Catalog grant SQL, Local dev environment (all four)

**Follow-up:** Cost estimate section confirmed — include rough per-run cost for Standard_F4s_v2 so readers understand the financial scope.

---

## LinkedIn Phase 1 Angle

| Option | Description | Selected |
|--------|-------------|----------|
| OIDC Workload Identity deep-dive | Hero: zero secrets in GitHub Actions. Security/DevSecOps angle. | |
| DABs IaC deep-dive | Hero: everything as code with Databricks Asset Bundles. | |
| Full foundation walkthrough | Hero: complete Azure Databricks Lakehouse foundation in one phase. | ✓ (via Other) |

**User's choice:** Full story narrative — "Phase 1: How to setup a full environment with [stack] using [tools]." Not a single-hook per article — covers the complete phase as a coherent story.

**Notes:** User explicitly preferred a full narrative over a narrow single-topic hook. Each phase article tells the complete story of that phase.

| Option | Description | Selected |
|--------|-------------|----------|
| Deep-dive with real YAML/config snippets | Show actual code, hiring managers can verify patterns. | ✓ |
| Conceptual overview with repo links | Shorter, broader audience. | |

**User's choice:** Deep-dive with real snippets (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Lead with Claude | Claude Code is the headline differentiator. | |
| Mention but don't lead | Technical DE story first, Claude gets a paragraph/callout. | ✓ |
| Keep it subtle | Just a footer mention. | |

**User's choice:** Mention but don't lead — "Claude should be the Robin in this Batman story."

---

## Claude's Discretion

- Auto-termination policy for interactive clusters (not applicable in Phase 1)
- Exact `make` target implementations beyond the three specified
- Order of topics in docs/setup.md
- Exact cost estimate numbers (use current Azure pricing at time of writing)

## Deferred Ideas

None.
