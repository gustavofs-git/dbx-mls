# Open decisions

Decisions deliberately left unresolved. Each states what is blocked by it and what the
options were when it was parked, so that resuming does not mean starting over.

## OD-1 — Public showcase

**Status:** parked by the project owner, 2026-10-09.

**Question.** Should the project publish a live, public dashboard, and if so, where?

**What was established before parking.**

The original plan had five hops: `consumption → Parquet export to a volume → GitHub Actions
downloads via the CLI → commit to a data branch → Streamlit Community Cloud reads it`. Two of
those hops can be removed: GitHub Actions can query the SQL warehouse directly with
`databricks-sql-connector`, writing a small file into the repository. That eliminates the
export job, the export volume, and the `databricks fs cp` dependency.

Options for where the dashboard lives:

| | Option | Always online | Extra platform | Effort |
|---|---|---|---|---|
| A | Static page on the existing GitHub Pages site, rendering from a committed JSON file | yes | none | medium — client-side charting |
| B | Streamlit Community Cloud reading the committed file | **no** — apps sleep after about seven days and show a wake screen | one | low — plain Python |
| C | Native Databricks dashboard, screenshots and video only | n/a | none | minimal |

The recommendation at the time of parking was **A plus C**: a static public page that cannot
hibernate, alongside native dashboard screenshots that evidence the platform work. A
portfolio link that greets a reader with "this app has gone to sleep" was considered the
decisive argument against B.

**What is blocked.** Epic 9 does not exist. Also deferred with it: the one earned
materialization in the consumption layer (`showcase_*`), and the schema contract test
asserting that published output contains no player identifier.

**What is not blocked.** Nothing in the current architecture depends on this. The consumption
layer is views only, which is the correct state either way.

**Relevant constraints.** Published output must be aggregated only, well under 100 MB, and
free of player identifiers — see [ADR-0010](../adr/0010-puuid-pseudonymization.md). Riot's
Developer Policy must be read while authenticated before anything is published.

## OD-2 — Riot personal API key

**Status:** awaiting Riot.

**Question.** Will Riot approve a personal key, which does not expire?

**Impact.** Approval removes the 24-hour renewal step and makes the weekly schedule run
unattended. Rejection is already handled: the platform treats an invalid credential as an
expected input condition and records a skip. No design change is required either way.

**Action.** Apply during Epic 0; record the outcome here.

## OD-3 — In-pipeline AI summary

**Status:** conditional on probe V12.

**Question.** Are SQL AI functions available on Free Edition?

**Impact.** If available, a weekly natural-language meta summary is generated from the
consumption layer, as ticket 7.3. If not, the feature is dropped and the limitation is
recorded rather than worked around. See [ADR-0016](../adr/0016-ai-usage-scope.md).
