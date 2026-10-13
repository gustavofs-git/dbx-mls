# ADR-0003 — Scope: KR Challenger solo queue, match detail and timeline

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The Riot API charges one request per match. A development key allows roughly 20 requests per
second and 100 per two minutes, which is about 50 sustained requests per minute. The binding
constraint, however, is not the rate limit but storage: a match detail payload is 200–500 KB
and a timeline payload is 2–5 MB.

An unbounded crawl would exhaust the Free Edition quota in a single run. Scope must therefore
be chosen, not maximized, and the choice must serve the business question.

Candidate scopes were evaluated against the question *"what does the meta look like at the
top of the ladder, and how does it move between patches?"*

## Decision

| Dimension | Value |
|---|---|
| platform | `kr` (regional routing `asia`) |
| ladder segment | Challenger only |
| queue | `RANKED_SOLO_5x5` (`queueId` 420) |
| players per run | ~300 (the full Challenger league) |
| matches sampled per player | 3 most recent |
| timeline | included |

Expected cost per run:

```
league-v4 challenger league        1 request
match ids, 1 per player          300 requests
~900 match ids, ~30% overlap  →  ~650 distinct matches
match detail + timeline          ~1,300 requests   ≈ 26 minutes at the rate limit
raw payload                      ~2.2 GB JSON  ≈ 250–350 MB compressed in Delta
```

Scope lives in `conf/ingestion_scope.yml` and is overridden per bundle target. Changing it is
a reviewed one-file change.

## Alternatives considered

**Challenger + Grandmaster (~1,000 players).** Rejected: roughly 3,500 distinct matches per
run, about 70 minutes of calls and over 1 GB per run compressed. The additional players do not
add an analytical dimension — they are the same question with more rows.

**Multiple tiers from Iron to Challenger.** This was the original plan, and it answers a
different and also good question: how the meta differs by skill bracket. Rejected in favour of
depth at the top, because KR Challenger is the leading indicator of the global meta and
because tier comparison requires sampling every tier, multiplying cost by five.

**Multiple regions.** Rejected for v1: region is a dimension worth adding only after the
single-region pipeline is proven, and it multiplies cost linearly.

**Excluding the timeline.** Rejected once the run cadence was reduced to weekly. The timeline
is what enables gold and experience curves, objective timing and first-blood impact — the
analyses that distinguish this from a champion win-rate table that already exists on a dozen
websites.

**Data Dragon as a primary source.** Rejected: static reference data demonstrates no
incremental ingestion, no deduplication and no accumulation of history. It is on the roadmap
as a dimension enrichment, not as a source.

## Consequences

- One run produces approximately 650 matches, 6,500 participant rows, 195,000 frame rows and
  300,000 filtered event rows.
- At a weekly cadence, two consecutive patches are covered within about a month, which is the
  minimum for any patch-over-patch comparison.
- The deliberate 30% match overlap between Challenger players is a real deduplication problem
  rather than a demonstration of one.
- Champion coverage at Challenger is narrower than at lower tiers: rare champions will have
  small sample sizes, and aggregate views must expose `matches_played` so that readers can
  judge significance. This is a documented analytical limitation, not a defect.
