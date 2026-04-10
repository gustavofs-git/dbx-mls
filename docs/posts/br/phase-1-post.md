# Post LinkedIn — Fase 1

Agentic Coding + Databricks — Dia 1

A Fase 1 é pura fundação sem nenhum dado ainda: autenticação sem segredos via OIDC Workload Identity Federation com dois Azure AD Federated Identity Credentials — branch-scoped para dev, environment-scoped com approval gate para prod — infraestrutura declarada em YAML com DABs, ownership dos schemas do Unity Catalog definido via SP desde o primeiro deploy do CI — não do laptop de ninguém —, e um smoke test permanente que valida API key, schemas e roundtrip de tabela Delta após cada deploy, bloqueando a transição para a Fase 2 se qualquer coisa estiver fora.
