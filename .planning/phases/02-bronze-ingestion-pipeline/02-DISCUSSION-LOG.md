# Phase 2: Bronze Ingestion Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-13
**Phase:** 02 — Bronze Ingestion Pipeline

---

## Gray Areas Identified

1. API fetch execution model
2. Partial failure recovery
3. LinkedIn Phase 2 article angle
4. `ingestion_log` observability depth

---

## Discussion Transcript

### Area 1: API Fetch Execution Model

**Q:** How should the API fetch loops execute?

**Options presented:**
- Driver-only Python loop (Recommended) — all API calls in a plain for-loop on the Spark driver
- Spark-distributed fetch — distribute PUUIDs/match IDs across workers for parallel HTTP
- You decide

**Selected:** Driver-only Python loop (Recommended)

**Rationale captured:** Rate limiter singleton shared naturally on driver. Sequential dependency chain (entries → match IDs → match raw) aligns with single-threaded driver execution. Spark is for Delta writes only.

---

### Area 2: Partial Failure Recovery

**Q:** When the ingestion job dies mid-run, what should the next run do?

**Options presented:**
- Restart clean, rely on MERGE (Recommended) — MERGE dedup handles idempotency
- Checkpoint-resume — track last processed offset, resume from there
- You decide

**Selected:** Restart clean, rely on MERGE (Recommended)

**Rationale captured:** Anti-join pre-check + MERGE means already-ingested matches cost zero API calls on restart. 4-hour timeout budget is sufficient. Simpler story to tell in portfolio.

---

### Area 3: LinkedIn Phase 2 Article Angle

**Q:** What's the narrative angle for the Phase 2 LinkedIn article?

**Options presented:**
- Full pipeline story (Recommended)
- Rate limiter technical deep-dive
- You decide

**Selected:** Other (user-provided input)

**User response:** "check @phase1br post and phase1br article. That was the first that i actually post. Based on that, see what i expect. The final output should be written with the information after we passed all human tests so it can be updated."

**Files reviewed:** `docs/posts/br/phase-1br-article.md`, `docs/posts/br/phase-1br-post.md`

**Decisions captured:**
- Full story format, same as Phase 1 BR article (technical deep-dive with real code snippets)
- Written AFTER UAT passes — real row counts and verified results must be incorporated
- Article generated in English first, then LPH agent humanizes/translates to Brazilian Portuguese

---

### Area 4: ingestion_log Depth

**Q:** The ROADMAP defines 7 fields. Any additions for portfolio storytelling?

**Options presented:**
- 7 fields is enough (Recommended)
- Add per-endpoint breakdown
- Add error details field

**Selected:** 7 fields is enough (Recommended)

**Rationale captured:** Defined fields cover runtime, volume, rate limit hits, and outcome. Additions risk scope creep.

---

## Summary

4 areas discussed, 4 decisions locked. No scope creep. No deferred ideas.
