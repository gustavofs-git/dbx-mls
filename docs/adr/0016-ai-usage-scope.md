# ADR-0016 — AI in the development process; in-pipeline AI optional; no ML in v1

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The project is developed with an AI coding agent, and the owner wants that to be part of what
the project demonstrates. Three distinct uses are available, and conflating them is the usual
failure: a project that adds a mediocre model to look modern weakens rather than strengthens.

## Decision

| | Use | Status |
|---|---|---|
| 1 | AI in the development process: agent-driven development with versioned skills standardizing commits, pull requests, ADRs and endpoint scaffolding; a validation subagent that probes platform capabilities | **In scope** |
| 2 | AI inside the pipeline: a SQL AI function generating a natural-language weekly meta summary from the consumption layer | **In scope if available on Free Edition** |
| 3 | Machine learning: predicting match outcome from minute-15 timeline features, tracked in MLflow | **Out of scope for v1; on the roadmap** |

For (1), the `CLAUDE.md`, the skill definitions and the subagent definition are versioned in
this repository, and the orchestration is documented so the claim is inspectable rather than
asserted.

## Alternatives considered

**Include the ML model in v1.** The timeline data makes it genuinely feasible, and win
prediction is a recognizable problem. Rejected on scope: the project is already large, the
model would compete for attention with the architectural thesis, and a model trained on about
8,000 matches from one tier would be mediocre — a mediocre model is worse than none.

**Skip in-pipeline AI entirely.** Rejected as a missed cheap opportunity, but it remains
conditional: if AI functions are unavailable on Free Edition, this is recorded as a platform
limitation rather than worked around.

**Treat agent-assisted development as an implementation detail not worth documenting.**
Rejected: how work is delegated to agents, what is reviewed by hand, and which standards are
enforced mechanically is one of the most differentiating things the project can show, and
almost no portfolio documents it.

## Consequences

- Skill and agent definitions are part of the deliverable and are maintained like code.
- The weekly summary feature is conditional, and its absence must be explained rather than
  silently dropped.
- The roadmap carries win prediction as an explicitly deferred item with a stated reason,
  which is stronger than an unexplained gap.
