# Phase 1: Infrastructure, Governance & CI/CD Foundation - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Provision the full Azure Databricks foundation: repo scaffold, DABs configuration, OIDC Workload
Identity CI/CD pipeline, Unity Catalog schema ownership (SP-owned from day one), Databricks Secrets,
and a permanent smoke-test job that validates end-to-end infra health.

This phase is purely infrastructure — no pipeline code, no Bronze/Silver tables, no data movement.
Everything delivered here is the prerequisite that every subsequent phase depends on.

</domain>

<decisions>
## Implementation Decisions

### Cluster Configuration

- **D-01:** Dev and prod job clusters both use `node_type_id: Standard_F4s_v2` (8 GB RAM, 4 vCPUs).
  Chosen for cost minimization — ~30% cheaper than Standard_DS3_v2, adequate for smoke test and
  Phase 1 validation.
- **D-02:** `autotermination_minutes: 0` on job clusters (they terminate when the job finishes —
  this is the correct job cluster pattern, not an oversight).
- **D-03:** Both `dev` and `prod` targets use the same VM size. No right-sizing difference between
  environments — keeps the config simple for a portfolio and avoids unnecessary complexity.

### Smoke Test

- **D-04:** The smoke test job (`resources/jobs/smoke_test_job.yml` + `notebooks/smoke_test.py`)
  is **permanent** — it stays in the bundle after Phase 1 and is not removed when pipeline code
  is added in later phases. It serves as an ongoing infrastructure health-check.
- **D-05:** `cd-dev.yml` automatically triggers the smoke test after every successful dev deploy.
  Every push to `main` follows: `databricks bundle deploy --target dev` → `databricks bundle run
  smoke_test_job --target dev` → assert exit 0. CI is green only if the workspace is healthy.
- **D-06:** Smoke test covers three validations: (1) Riot API key retrievable via
  `dbutils.secrets.get(scope="lol-pipeline", key="riot-api-key")` with redacted log output,
  (2) `SHOW SCHEMAS IN lol_analytics` confirms UC catalog access, (3) a temp Bronze table
  roundtrip (`lol_analytics.bronze.smoke_test` created, read, dropped).

### Setup Documentation (`docs/setup.md`)

- **D-07:** Written as a **lean reference guide**, not a step-by-step tutorial. Assumes the
  reader has an Azure subscription and a Databricks workspace. This is a replication guide —
  reviewers must provision their own infrastructure. The repo demonstrates patterns; it does
  not provide a shared live environment.
- **D-08:** The doc explicitly states that the author's clusters are private and cost-incurring —
  reviewers cannot connect to them. To run this pipeline, the reader must provision their own
  Azure Databricks workspace and bear the Azure compute costs.
- **D-09:** Include a **cost estimate section** with rough per-run costs for Standard_F4s_v2
  (e.g., smoke test ~$0.05–0.10 per CI run, Phase 1 full deploy ~$0.50–1.00). Honest framing
  that the total Phase 1 spend should be under $5 for a typical setup run.
- **D-10:** `docs/setup.md` must cover all four topics:
  1. **OIDC federation setup** — step-by-step for creating the SP, OIDC federation policies
     (dev: branch-scoped, prod: environment-scoped), and GitHub repository variables
  2. **Unity Catalog grant SQL** — the exact `GRANT` statements to run once as workspace admin
     to give the SP schema ownership on `bronze`, `silver`, and `gold`
  3. **Riot API key rotation** — how to get/renew the dev key (24h expiry), how to update the
     Databricks Secret, and where to register for a permanent production key
  4. **Local dev environment** — Databricks CLI install + `databricks auth login`, Python env
     setup, Java 11 for pytest local, and available `make` targets

### LinkedIn Phase 1 Deliverable

- **D-11:** Article format: **full story narrative** — "Phase 1: How I built a full Azure
  Databricks Lakehouse foundation with OIDC, DABs, and Unity Catalog." Not a single-topic
  deep-dive — covers the complete Phase 1 scope as a coherent story.
- **D-12:** **Deep-dive with real code snippets** — include actual YAML from `databricks.yml`,
  GitHub Actions workflow blocks, federation policy format, UC grant SQL. Hiring managers can
  verify the patterns by reading the article alone.
- **D-13:** **Claude as Robin, not Batman.** The article is primarily a technical DE story.
  Claude Code gets a paragraph mention (e.g., a callout or "how I built this" section) — not
  the headline. The human engineer's architecture decisions and reasoning are the hero.
- **D-14:** Short post (summary version): ~150 words, links to the full article and the GitHub
  repo. Highlights the OIDC zero-secrets angle as the punchy hook for the summary format.

### Claude's Discretion

- Auto-termination policy for any interactive clusters (not applicable in Phase 1 — job clusters only)
- Exact `make` target implementations beyond `validate`, `test`, `smoke`
- `resources/clusters.yml` exact `spark.databricks.cluster.profile` value (singleUser is specified in roadmap)
- Order of topics in `docs/setup.md` — structure to Claude's judgment
- Exact phrasing of cost disclaimer and the cost estimate numbers (use best available Azure pricing at time of writing)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — INFRA-01 through INFRA-07, CICD-01 through CICD-06 (full acceptance criteria for Phase 1)
- `.planning/ROADMAP.md` §Phase 1 — Four plan definitions with exact deliverables, file paths, acceptance criteria, and critical pitfalls

### Project Architecture
- `.planning/PROJECT.md` — Core value, constraints, key decisions table, out-of-scope items

### Critical Constraints (read STATE.md for context)
- `.planning/STATE.md` §Accumulated Context — Phase 1 SP ownership constraint, OIDC subject claim case-sensitivity pitfall

No external specs — requirements fully captured in decisions and planning artifacts above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield repo. No existing code to reuse.

### Established Patterns
- None — this phase establishes the patterns that all subsequent phases follow.

### Integration Points
- `databricks.yml` is the root bundle file — all subsequent phases add jobs/resources via `include:` entries
- `resources/schemas.yml` created in Phase 1 defines the UC catalog/schema structure that Bronze and Silver phases write to
- `.github/workflows/` established in Phase 1 is extended in later phases (not replaced)
- `docs/posts/` directory created in Phase 1 receives LinkedIn deliverables from all 5 phases

</code_context>

<specifics>
## Specific Ideas

- **Cost-first framing in docs:** User is explicit about minimizing Azure spend. All cluster configs, docs, and cost estimates should reflect this constraint. Standard_F4s_v2 is the deliberate choice.
- **"Bring your own Azure" language in docs/setup.md:** The doc should make clear upfront that this repo is a pattern demonstration, not a shared service. Reviewers run their own instance.
- **Claude as Robin:** In the LinkedIn article, Claude Code gets a supporting mention (not the lead). The article narrative is the engineer's story, Claude is a tool they used.
- **Full story vs single-hook article:** Phase 1 article covers the complete foundation — OIDC + DABs + UC governance + smoke test — as one coherent narrative, not a narrow topic deep-dive.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 1 scope.

</deferred>

---

*Phase: 01-infrastructure-governance-ci-cd-foundation*
*Context gathered: 2026-04-07*
