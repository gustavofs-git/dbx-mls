# ADR-0009 — Native pipeline expectations rather than Great Expectations or Soda

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

Data quality enforcement needs a mechanism. The main options are the expectations built into
Lakeflow declarative pipelines, or an external framework such as Great Expectations or Soda
Core added as a Python dependency.

## Decision

Use native pipeline expectations as the enforcement mechanism, and write measurements to
`ops.dq_metrics` for the dashboard.

Expectations are declared as class attributes on each transform, so the rule sits beside the
code that produces the column it checks.

## Alternatives considered

**Great Expectations.** Far richer: a large battery of expectation types, data docs, profiling
and a suite abstraction. Rejected for three reasons. It cannot *act* inside the pipeline —
it validates a DataFrame and reports, but dropping or failing still has to be wired by hand,
duplicating what expectations do natively. Its dependency footprint and configuration surface
are large relative to a project with roughly a dozen rules. And it would sit outside Unity
Catalog, so quality results would not appear alongside pipeline lineage and run history.

**Soda Core.** Lighter than Great Expectations and pleasant to configure in YAML. Rejected for
the same structural reason: checks run as a separate step, so enforcement remains manual, and
results live outside the platform.

**Hand-written filters and counts.** Rejected: that is precisely the plumbing the native
mechanism removes, and per-rule failure counting written by hand is exactly where such code
develops bugs.

## Consequences

- Quality rules are limited to what expectations express: a SQL boolean per row, with drop,
  fail or warn semantics. Distribution checks, cross-table reconciliation and profiling are
  not available natively and are implemented as explicit measurements in
  `src/mls/quality/metrics.py` writing to `ops.dq_metrics`.
- Rules cannot be unit tested off-platform, because they are strings evaluated by the pipeline
  runtime. They are covered by integration tests that feed known-bad fixtures through the dev
  target and assert the resulting drop counts.
- Quality results are visible in the pipeline UI alongside lineage, with no extra deployment.
- Adding Great Expectations later remains possible as a profiling and documentation layer
  without replacing enforcement. It is on the roadmap as an optional extra, not a gap.
