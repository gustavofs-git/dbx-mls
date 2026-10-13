# ADR-0017 — One long-form article instead of a series of posts

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The original plan was for each project milestone to produce a short post explaining the
decisions made at that stage. The alternative is a single long-form article presenting the
architecture as one coherent argument.

## Decision

Publish one long-form article, carrying the project's thesis: two physical layers with a
`VARIANT` raw layer and a virtual consumption layer, with the trade-offs stated in both
directions.

ADRs continue to be written during development, at the moment each decision is made. They are
the article's raw material, and the article is assembled from them rather than written from
memory at the end.

## Alternatives considered

**A series of posts, one per milestone.** Maintains visible momentum and is easier to write in
small pieces. Rejected: it fragments a single argument across posts that are read
independently and incompletely, it is a recurring obligation competing with building the
thing, and the interesting claim — that the third layer should be earned rather than assumed
— only makes sense when the whole design is on the page.

**Only documentation, no article.** Rejected: the documentation site is written for someone
already looking at the project, while the article is what brings them there.

**Write the article at the end, from memory.** Rejected: reasoning decays, and reconstructed
rationale is recognizably thinner than rationale recorded at the moment of the decision.

## Consequences

- Writing an ADR is part of the definition of done for any decision, and this is enforced by
  the pull request checklist.
- There is no publication milestone until the project is substantially complete, so progress
  is not externally visible during development. Accepted.
- The article must present the counter-arguments, including the case for a materialized gold
  layer, or it reads as advocacy rather than engineering.
