---
quick_task: 260410-9jp
type: documentation-fix
subsystem: docs
tags: [documentation, oidc, azure-ad, phase-1, linkedin]
files_modified:
  - docs/posts/phase-1-article.md
  - docs/posts/phase-1-post.md
  - docs/posts/br/phase-1-article.md
  - docs/posts/br/phase-1-post.md
decisions:
  - "Azure OIDC flow in docs now accurately reflects implementation: GitHub OIDC -> azure/login@v2 -> Azure AD -> DATABRICKS_AUTH_TYPE: azure-cli"
  - "Federation setup documented as Azure AD Federated Identity Credentials on App Registration, not Databricks Account Console CLI commands"
  - "Three GitHub variables documented everywhere (DATABRICKS_HOST, DATABRICKS_CLIENT_ID, AZURE_TENANT_ID)"
metrics:
  completed: "2026-04-10"
  tasks: 2
  files_modified: 4
---

# Quick Task 260410-9jp: Fix Phase 1 Documentation to Match Implementation

One-liner: Corrected all four Phase 1 docs (EN + PT article and LinkedIn post) to reflect the implemented Azure OIDC flow — `azure/login@v2` + `DATABRICKS_AUTH_TYPE: azure-cli` + Azure AD Federated Identity Credentials — replacing the originally-planned Databricks-native OIDC flow that was never used.

## What Changed

The Phase 1 documents were written before an auth pivot: the originally-planned Databricks-native OIDC (`github-oidc` auth type, `databricks account service-principal-federation-policy create`) was replaced by Azure OIDC (`azure/login@v2` + `azure-cli` auth type, Azure AD Federated Identity Credentials). The docs described the planned approach, not the implemented one. A reader following the article would have failed to reproduce the project.

## Corrections Applied (EN and PT)

**Auth flow description:**
- Before: GitHub token presented to Databricks token endpoint (`/oidc/v1/token`), Databricks emits bearer token
- After: GitHub OIDC token -> `azure/login@v2` -> Azure AD access token -> `DATABRICKS_AUTH_TYPE: azure-cli` -> Databricks CLI uses Azure AD identity

**Federation setup:**
- Before: Two `databricks account service-principal-federation-policy create` CLI blocks
- After: Two Azure AD Federated Identity Credentials on the App Registration (`az ad app federated-credential create`), with correct `audiences: ["api://AzureADTokenExchange"]`

**CI YAML block (exact match to `.github/workflows/ci.yml`):**
- Before: `DATABRICKS_AUTH_TYPE: github-oidc`, `DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}`, no `azure/login` step
- After: `DATABRICKS_AUTH_TYPE: azure-cli`, `BUNDLE_VAR_sp_client_id: ${{ vars.DATABRICKS_CLIENT_ID }}`, `azure/login@v2` step with `client-id`, `tenant-id`, `allow-no-subscriptions: true`

**GitHub variables:**
- Before: Two variables (DATABRICKS_HOST, DATABRICKS_CLIENT_ID)
- After: Three variables (DATABRICKS_HOST, DATABRICKS_CLIENT_ID, AZURE_TENANT_ID) with purpose of each explained

**cd-dev.yml and cd-prod.yml descriptions:** Updated to note both also use `azure/login@v2` + `azure-cli` auth pattern.

**Lessons Learned Lesson 1:**
- Before: "Test with a `databricks auth login` attempt"
- After: Subject is in Azure AD Federated Identity Credential; verify with `az ad app federated-credential list --id <app-object-id>`

**LinkedIn posts:**
- Before: "Two federation policies: branch-scoped for dev CI..."
- After: "Two Azure AD Federated Identity Credentials: branch-scoped for dev CI..."

## Commits

- `7882e76` — fix(quick-260410-9jp-01): correct EN article and post
- `6319076` — fix(quick-260410-9jp-01): correct BR article and post (new files, previously not tracked)

## Deviations from Plan

**[Rule 3 - Blocking] BR files were not git-tracked.**
- Found during: Task 2 commit
- Issue: `docs/posts/` is in `.gitignore`. EN files were force-added previously (tracked). BR files had never been committed so were untracked+ignored.
- Fix: Used `git add -f` to force-add BR files, matching the existing pattern for EN files.
- Files modified: none extra

## Self-Check: PASSED

- `docs/posts/phase-1-article.md` — exists, `github-oidc` count = 0, `azure-cli` count = 5
- `docs/posts/phase-1-post.md` — exists, contains "Azure AD Federated Identity Credentials"
- `docs/posts/br/phase-1-article.md` — exists, `github-oidc` count = 0, `azure-cli` count = 5
- `docs/posts/br/phase-1-post.md` — exists, contains "Azure AD Federated Identity Credentials"
- Commits `7882e76` and `6319076` verified in git log
