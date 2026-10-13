# ADR-0013 — Documentation as code, published with MkDocs Material

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The project must be documented as if it were delivered to a company: architecture, data
model, decisions, runbook. Documentation also has a second audience here — a reader
evaluating the work — so it needs to be readable without cloning the repository.

## Decision

Documentation is Markdown under `docs/`, in the same repository and the same pull requests
as the code, published as a static site by MkDocs Material through GitHub Pages.

Architecture decisions use the MADR format, numbered and immutable: a record is superseded,
never rewritten.

## Alternatives considered

**Confluence Cloud Free.** Free up to ten users and familiar from corporate practice.
Rejected: it lives outside the repository, so it is never reviewed alongside the change it
describes — which is the mechanism by which documentation rots. It is also not publicly
readable, which defeats the second audience.

**GitHub Wiki.** Free and built in. Rejected: it is a separate git repository, so wiki edits
do not appear in the pull request that changes the behaviour being documented.

**Notion.** Pleasant to write in. Rejected for the same reason as Confluence, plus it would
become a second source of truth.

**Markdown in the repository with no published site.** Viable and nearly chosen. Rejected
because the published site costs about fifteen lines of configuration and one workflow, and
provides search, navigation and rendered Mermaid diagrams.

## Consequences

- The definition of done for any change that alters behaviour includes updating the
  documentation in the same pull request.
- Documentation changes are reviewed, versioned and attributable like code.
- The accumulated ADRs are the raw material for the long-form article; no separate writing
  effort is required to produce it. See
  [ADR-0017](0017-single-article-over-post-series.md).
- MkDocs Material and its Mermaid configuration become a build dependency, pinned in the
  project's dependency file.
