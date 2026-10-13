# Ways of working

The process is deliberately heavier than a personal project needs, because reproducing a
professional delivery is part of what is being demonstrated. Every mechanism below is one a
working team would have.

## Issue hierarchy

```
Initiative   mylolstats — a portfolio data platform on Databricks Free Edition
└── Epic     Epic 4 — Harmonized
    └── Ticket   4.4 Build matches, match_participants and match_teams
```

Implemented with GitHub Issues sub-issues. Labels: `epic:<n>`, `layer:<bronze|harmonized|
consumption|ops>`, `type:<feat|fix|docs|chore|refactor|test>`, `blocked`, `needs-validation`.

A ticket is refined enough to start when it states its acceptance criteria and names the
probe or ADR it depends on.

## Branches, commits, pull requests

| | Convention |
|---|---|
| branch | `<type>/<issue>-<slug>` — `feat/42-harmonized-match-participants` |
| commit | Conventional Commits with a scope from a fixed list — `feat(harmonized): add match_participants transform` |
| pull request | imperative title, `Closes #<n>` in the body, the checklist below completed |

Fixed commit scopes, so history stays greppable: `landing`, `bronze`, `harmonized`,
`consumption`, `ops`, `ingest`, `riot`, `bundle`, `ci`, `docs`, `tests`.

## Definition of done

Every pull request carries this checklist, and it is not a formality — a box that cannot be
ticked is a reason not to merge.

- [ ] `ruff check` and `ruff format --check` pass
- [ ] unit tests cover the new pure logic; `pytest` passes
- [ ] `databricks bundle validate` passes
- [ ] documentation updated **in this pull request**, not later
- [ ] an ADR exists if an architectural decision was made or changed
- [ ] Unity Catalog comments written for any new table or column
- [ ] no secret, token or salt in the diff
- [ ] no raw `puuid` reaches the harmonized layer or beyond
- [ ] quota impact considered and stated if non-trivial

## Agent tooling

Development is agent-assisted. The definitions are versioned in this repository, so the claim
is inspectable rather than asserted.

### Skills

| Skill | Standardizes | Corporate equivalent |
|---|---|---|
| `/commit` | Conventional Commits message, valid scope, issue reference | commit-msg hook |
| `/open-pr` | pull request from the template, checklist, labels, `Closes #<n>` | mandatory PR template |
| `/new-adr` | MADR record with the next number, index updated | architecture review process |
| `/new-endpoint` | scaffolds an endpoint: ingestor, transform, registry entry, tests, DDL | internal cookiecutter |
| `/new-ticket` | issue in the correct place in the hierarchy, with type and labels | refinement standard |

### Subagent

| Subagent | Role |
|---|---|
| `dbx-validator` | runs capability probes against the workspace and reports results into the [validation plan](../operations/validation-plan.md). It exists to enforce the rule that no Free Edition capability is assumed |

Deliberately **not** created: a code-review subagent, which would duplicate tooling that
already exists, and a "data modeler" subagent, because modeling decisions are made in
discussion and recorded as ADRs — an agent for that would be decorative.

### `CLAUDE.md`

Carries the conventions an agent must not rediscover each session: naming, package structure,
the rule that logic never lives inside a `@dlt` decorator, the prohibition on committing
secrets, and the definition of done.

## Review

Every change goes through a pull request, including solo work. The reviewer is the author,
assisted by `/code-review`. The point is not gatekeeping — it is that the diff, the
checklist and the rationale exist as a record, which is the artefact being produced.

## Decision records

A decision is recorded when it is made, not reconstructed afterwards. Records are immutable:
a change of mind produces a new record that supersedes the old one. Reasoning decays quickly,
and recovered rationale is recognizably thinner than rationale captured at the time.
