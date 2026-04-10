Nota: Este artigo é um resumo técnico gerado por IA (Claude Code) com base nos artefatos e decisões da Fase 1 do projeto dbx-mls. O conteúdo reflete implementações reais — arquitetura, configurações e código — mas a narrativa e estrutura foram produzidas automaticamente.

---

Fase 1: Fundação do Lakehouse Azure Databricks — OIDC, DABs e Unity Catalog

O que foi entregue

A Fase 1 estabeleceu a fundação completa de infraestrutura do projeto dbx-mls. Nenhum dado de League of Legends foi ingerido ainda — o objetivo era exclusivamente garantir que a infraestrutura estivesse pronta para produção antes de qualquer código de pipeline.

Entregas concretas:

- Autenticação sem credenciais armazenadas via OIDC Workload Identity Federation com dois escopos de confiança distintos (branch-scoped para dev, environment-scoped para prod)

- Infraestrutura como código com Databricks Asset Bundles (DABs) declarando jobs, clusters e schemas em YAML versionado

- Unity Catalog com ownership correto desde o primeiro deploy — schemas criados pelo Service Principal via CI, não por desenvolvedor via laptop

- Smoke test permanente validando API key, schemas UC e roundtrip Delta após cada deploy de dev

- Pipeline CI/CD com três workflows GitHub Actions sem nenhum secret armazenado no repositório

---

Autenticação: OIDC Workload Identity Federation

Por que não PAT

PATs são credenciais de longa duração vinculadas a um usuário individual. Problemas concretos em ambiente enterprise: rotação manual, escopo workspace-wide, expiram com o desligamento do usuário, aparecem em logs acidentalmente. Um PAT vazado exige auditoria de todo o workspace.

Como o OIDC funciona aqui

O GitHub Actions solicita um token OIDC de curta duração do IdP do GitHub em runtime. Esse token é passado para `azure/login@v2`, que autentica junto ao Azure AD e recebe um access token do Azure para o Service Principal. A Databricks CLI então usa `DATABRICKS_AUTH_TYPE: azure-cli` para obter acesso ao workspace via Azure AD — o token não é enviado diretamente para um endpoint do Databricks. Nenhuma credencial é persistida em nenhum lugar.

O relacionamento de confiança que torna isso possível é configurado como Federated Identity Credentials no App Registration no Azure AD — não via comandos CLI do Databricks Account Console. Duas credentials são criadas (via Azure portal ou `az ad app federated-credential create`):

```bash
# Credential dev — branch-scoped: confia em qualquer run originada da branch main
az ad app federated-credential create --id <app-object-id> --parameters ‘{
  “name”: “github-dev”,
  “issuer”: “https://token.actions.githubusercontent.com”,
  “subject”: “repo:<org>/dbx-mls:ref:refs/heads/main”,
  “audiences”: [“api://AzureADTokenExchange”]
}’

# Credential prod — environment-scoped: exige GitHub Environment com approval gate
az ad app federated-credential create --id <app-object-id> --parameters ‘{
  “name”: “github-prod”,
  “issuer”: “https://token.actions.githubusercontent.com”,
  “subject”: “repo:<org>/dbx-mls:environment:prod”,
  “audiences”: [“api://AzureADTokenExchange”]
}’
```

Duas Federated Identity Credentials do Azure AD servem dois limites de confiança distintos. A credential de dev confia em qualquer push para a branch `main`. A credential de prod confia apenas em jobs executando dentro do GitHub Environment `prod` — que requer aprovação humana explícita antes de rodar.

O `subject` claim é o ponto crítico. Para dev, o formato `ref:refs/heads/main` corresponde a qualquer job em push para main. Para prod, `environment:prod` corresponde apenas a jobs dentro do GitHub Environment `prod`.

Atenção: o match do `subject` é case-sensitive. `environment:prod` e `environment:Prod` são strings distintas. Um mismatch retorna 401 sem mensagem de erro diagnóstica. O subject está configurado na Federated Identity Credential do Azure AD — verifique com `az ad app federated-credential list --id <app-object-id>` antes de fazer push para CI.

O GitHub Actions usa três variáveis de repositório (`DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `AZURE_TENANT_ID`) — sem secrets. `DATABRICKS_CLIENT_ID` é o UUID de aplicação do SP no Azure AD (usado pelo `azure/login` como client ID e pelo bundle como identidade `run_as`). `AZURE_TENANT_ID` é o UUID do tenant do Azure AD, exigido pelo `azure/login@v2`. As três são não-sensíveis (UUIDs e URLs) e seguras em variáveis em vez de secrets.

---

Databricks Asset Bundles

Estrutura do bundle

O `databricks.yml` é o ponto de entrada do bundle e declara targets e variáveis:

```yaml
bundle:
  name: dbx-mls
  databricks_cli_version: “>=0.250.0”

include:
  - resources/jobs/*.yml
  - resources/schemas.yml

variables:
  sp_client_id:
    description: “Client ID (UUID) do Service Principal usado para run_as em prod”

permissions:
  - service_principal_name: ${var.sp_client_id}
    level: CAN_MANAGE

targets:
  dev:
    default: true
    workspace:
      root_path: /Workspace/Users/${var.sp_client_id}/.bundle/dbx-mls/dev

  prod:
    mode: production
    workspace:
      root_path: /Workspace/Shared/.bundle/dbx-mls/prod
    run_as:
      service_principal_name: ${var.sp_client_id}
```

O `include:` lista explicitamente os jobs e o arquivo de schemas — `resources/jobs/*.yml` captura automaticamente novos jobs adicionados nas fases seguintes sem alterar o bundle raiz. O bloco `permissions:` garante que o SP tenha `CAN_MANAGE` sobre o path do bundle deployado; sem ele, o job cluster não consegue acessar os artefatos em runtime. O target de dev não usa `mode: development` — esse flag foi removido porque gera paths com prefixo de usuário que o SP não consegue acessar; em vez disso, o dev usa um `root_path` fixo no diretório do próprio SP no workspace. O `run_as` no target prod garante que jobs de produção executem sob identidade do SP — não do usuário que disparou o deploy — requisito de auditoria em ambientes enterprise.

Limitação conhecida da CLI v0.295.0

`workspace.host` não aceita interpolação de variável quando definido no `databricks.yml`. A CLI rejeita a sintaxe `${var.host}` para campos de autenticação. O padrão correto é definir `DATABRICKS_HOST` como variável de ambiente no bloco `env` do workflow — nunca no arquivo do bundle.

Schemas como recursos gerenciados

```yaml
resources:
  schemas:
    bronze:
      catalog_name: lol_analytics
      name: bronze
      comment: “Raw Riot API JSON responses — Bronze layer (dbx-mls)”
    silver:
      catalog_name: lol_analytics
      name: silver
      comment: “Schema-enforced typed Delta tables — Silver layer (dbx-mls)”
    gold:
      catalog_name: lol_analytics
      name: gold
      comment: “Analytics aggregations — Gold layer (dbx-mls)”
```

Declarar schemas como recursos DAB significa que `databricks bundle deploy` os reconcilia em todo deploy. Adicionar um novo job na Fase 2 exige apenas um novo arquivo em `resources/jobs/` — sem tocar no bundle raiz.

---

Unity Catalog: Bootstrap de Ownership

O problema de ordem de deploy

O Unity Catalog atribui ownership na criação: a identidade que executa `CREATE SCHEMA` torna-se owner do schema. Se um desenvolvedor rodar `databricks bundle deploy` do laptop antes do CI, os schemas ficam sob identidade humana. O Service Principal não tem permissão para modificar schemas que não são seus — e corrigir isso sem dropar e recriar os schemas é trabalhoso.

Sequência correta de bootstrap

Um admin executa os grants abaixo uma única vez, antes do primeiro deploy via CI:

```sql

GRANT USE CATALOG   ON CATALOG lol_analytics TO `<sp-application-id>`;

GRANT CREATE SCHEMA ON CATALOG lol_analytics TO `<sp-application-id>`;

GRANT USE SCHEMA    ON SCHEMA lol_analytics.bronze TO `<sp-application-id>`;

GRANT CREATE TABLE  ON SCHEMA lol_analytics.bronze TO `<sp-application-id>`;

GRANT MODIFY        ON SCHEMA lol_analytics.bronze TO `<sp-application-id>`;

GRANT USE SCHEMA    ON SCHEMA lol_analytics.silver TO `<sp-application-id>`;

GRANT CREATE TABLE  ON SCHEMA lol_analytics.silver TO `<sp-application-id>`;

GRANT MODIFY        ON SCHEMA lol_analytics.silver TO `<sp-application-id>`;

GRANT USE SCHEMA    ON SCHEMA lol_analytics.gold TO `<sp-application-id>`;

GRANT CREATE TABLE  ON SCHEMA lol_analytics.gold TO `<sp-application-id>`;

GRANT MODIFY        ON SCHEMA lol_analytics.gold TO `<sp-application-id>`;

```

Após o CI fazer o primeiro deploy, o SP cria os schemas e ownership está correto. Verificação:

```sql

SHOW GRANTS ON SCHEMA lol_analytics.bronze;

```

O `owner` deve ser o application UUID do SP — não um e-mail. E-mail de humano indica que o schema foi criado localmente primeiro.

---

GitHub Actions: Três Workflows, Zero Secrets

`ci.yml` — validação em todo push

```yaml
permissions:
  id-token: write   # sem essa linha o GitHub não emite o token OIDC
  contents: read

jobs:
  validate-and-test:
    runs-on: ubuntu-latest
    env:
      DATABRICKS_AUTH_TYPE: azure-cli
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      BUNDLE_VAR_sp_client_id: ${{ vars.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.DATABRICKS_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          allow-no-subscriptions: true
      - uses: actions/setup-python@v5
        with:
          python-version: “3.12”
      - run: pip install -r requirements-dev.txt
      - uses: databricks/setup-cli@v0.295.0
      - run: databricks bundle validate
      - run: pytest tests/unit/ --cov=src --cov-report=xml
```

`azure/login@v2` troca o token OIDC do GitHub por um access token do Azure AD em nome do Service Principal. `DATABRICKS_AUTH_TYPE: azure-cli` instrui a Databricks CLI a usar a credencial do Azure CLI (configurada pelo `azure/login`) em vez de tentar PAT lookup ou OIDC nativo do Databricks. `BUNDLE_VAR_sp_client_id` fornece a variável de bundle `sp_client_id` exigida pelo bloco `run_as` do target prod.

`cd-dev.yml` — deploy dev em push para main

Também usa `azure/login@v2` + `DATABRICKS_AUTH_TYPE: azure-cli` e passa `BUNDLE_VAR_sp_client_id` e `AZURE_TENANT_ID` no env. Sem chave `environment:` — intencionalmente. Sem `environment:`, o `subject` claim do token OIDC usa o formato `ref:refs/heads/main`, que bate com a Federated Identity Credential de dev. Adicionar `environment:` mudaria o formato do subject e quebraria o match.

`cd-prod.yml` — deploy prod em tags de versão

Também usa `azure/login@v2` + `DATABRICKS_AUTH_TYPE: azure-cli`.

```yaml
environment: prod   # case-sensitive — deve bater exatamente com o subject da Federated Identity Credential
concurrency:
  group: prod-deploy
  cancel-in-progress: false  # deploy em andamento não é cancelado por push mais recente
```

`cancel-in-progress: false` é deliberado: um deploy de prod em progresso não deve ser interrompido. O push mais recente entra na fila.

---

Smoke Test: Gate de Aceitação da Fase 1

O smoke test é fixture permanente — não é removido nas fases seguintes. Roda após todo deploy de dev e responde: o workspace está funcional?

Validação 1 — Riot API key recuperável do Databricks Secrets:

```python

api_key = dbutils.secrets.get(scope=”lol-pipeline”, key=”riot-api-key”)

assert len(api_key) > 0, “riot-api-key retornou string vazia — verifique o valor do secret”

print(”Validação 1 OK: Riot API key recuperada (valor redactado nos logs)”)

```

O Databricks redacta automaticamente o valor em logs — apenas `[REDACTED]` aparece.

Validação 2 — Unity Catalog acessível e schemas presentes:

```python

schemas_df = spark.sql(”SHOW SCHEMAS IN lol_analytics”)

schema_names = [row[”databaseName”] for row in schemas_df.collect()]

assert “bronze” in schema_names, f”schema bronze não encontrado. Encontrado: {schema_names}”

assert “silver” in schema_names, f”schema silver não encontrado. Encontrado: {schema_names}”

assert “gold”   in schema_names, f”schema gold não encontrado. Encontrado: {schema_names}”

print(f”Validação 2 OK: schemas UC confirmados: {schema_names}”)

```

Validação 3 — Roundtrip Delta em bronze (create / insert / read / drop):

```python

spark.sql(”DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test”)

spark.sql(”CREATE TABLE lol_analytics.bronze.smoke_test (id BIGINT, msg STRING) USING DELTA”)

spark.sql(”INSERT INTO lol_analytics.bronze.smoke_test VALUES (1, ‘smoke’)”)

result = spark.sql(”SELECT COUNT(*) as cnt FROM lol_analytics.bronze.smoke_test”).collect()[0][”cnt”]

assert result >= 1, f”Esperado ≥1 linha, encontrado {result}”

spark.sql(”DROP TABLE IF EXISTS lol_analytics.bronze.smoke_test”)

print(”Validação 3 OK: roundtrip Delta bronze (create/insert/read/drop) bem-sucedido”)

```

Qualquer falha nas três validações bloqueia a run de CI e impede transição para a Fase 2.

---

Stack e Versões

| Componente | Versão / Detalhe |

|---|---|

| Databricks CLI | `>=0.250.0` (pinado em `0.295.0` nos workflows) |

| Databricks Runtime | 16.4 LTS |

| Python | 3.12 |

| GitHub Actions | `actions/checkout@v4`, `setup-python@v5` |

| Unity Catalog | `lol_analytics` catalog, 3 schemas (bronze/silver/gold) |

| Autenticação | OIDC Workload Identity Federation, sem PAT |

---

O Que Vem na Fase 2

A Fase 2 constrói sobre essa fundação: ingestão da Riot Games API, rate limiter dual-bucket para respeitar os limites da API, e as primeiras tabelas Delta reais em `lol_analytics.bronze`. O smoke test continua rodando após cada deploy de dev — agora acompanhado pelas definições dos jobs de ingestão.