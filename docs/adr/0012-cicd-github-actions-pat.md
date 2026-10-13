# ADR-0012 — GitHub Actions; CI does not write to the workspace on pull requests

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The project owner is not a DevOps specialist and asked for the simplest free option. Two
resources are genuinely scarce and shape the design: **Databricks compute quota**, where
exceeding the daily allowance disables compute until the next day, and the **personal access
token**, which is the most sensitive credential in the project.

A naive pipeline that deploys and runs integration tests on every push would consume quota
during the working day — exactly when it is needed for development — and would expose the
token on every pull request.

## Decision

Four workflows, with workspace writes confined to merges and to explicit manual runs.

| Workflow | Trigger | Steps | Touches the workspace |
|---|---|---|---|
| `ci.yml` | pull request | `ruff check`, `ruff format --check`, `pytest`, `databricks bundle validate -t prod` | no |
| `deploy.yml` | push to `main` | `databricks bundle deploy -t prod` | yes |
| `integration.yml` | manual + weekly | deploy `-t dev`, run the dev job at minimum scope, assert resulting tables | yes |
| `docs.yml` | push to `main` on `docs/**` | `mkdocs gh-deploy` | no |

Authentication is a Databricks personal access token stored in GitHub Secrets as
`DATABRICKS_TOKEN`, used only by `deploy.yml` and `integration.yml`.

Development deploys to the `dev` target are run from the developer's terminal, not from CI.

## Alternatives considered

**Deploy to `dev` and run integration tests on every pull request.** The textbook answer, and
better in an environment with elastic compute. Rejected: fifteen pushes in a working day would
consume the daily quota in CI, leaving none for development, and it would expose the token on
every pull request including forks. The scarce resource here is Databricks compute, not CI
minutes.

**Everything manual, no automated deployment.** Rejected: it breaks the requirement that jobs
are delivered through a pipeline, and manual deployment drifts from the repository.

**OAuth M2M with a service principal.** The correct production answer, and what this would use
with a budget. Rejected as almost certainly unavailable: Free Edition has no account console
and no account-level APIs, which is where service principals are managed. This is recorded as
a deviation rather than a recommendation, and the README states what production would do
instead. To be confirmed in the [validation plan](../operations/validation-plan.md).

## Consequences

- A pull request gets fast feedback — lint, unit tests and YAML validation — without
  consuming Databricks quota.
- Errors that only appear in the workspace are caught on merge or in the weekly integration
  run, not on the pull request. This is an accepted detection delay.
- The token is used in two workflows, both on protected paths. Token rotation is a runbook
  step.
- The repository is public, which makes GitHub Actions free and unlimited and serves the
  portfolio purpose. Secrets are never exposed to pull requests from forks because no
  secret-consuming workflow runs on `pull_request`.
