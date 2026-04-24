# Análise da Esteira de Deploy de Aplicações

> **Data:** Abril 2026
> **Escopo:** `deploy_all_dm_applications.yml` — streaming, DABs, Lambda
> **Objetivo:** Validar e tornar a esteira 100% operacional em PRD (2 deploys consecutivos sem erro)

---

## 1. Visão Geral da Esteira

O workflow `deploy_all_dm_applications.yml` orquestra o deploy dos três tipos de aplicação em um único pipeline coordenado:

```
┌─────────────────────────────────────────────────────────────┐
│  FASE 1 — CHECK                                             │
│  • Branch guard (develop only)                              │
│  • Versão: valida v{VERSION}, v{VERSION}-dabs, v{VERSION}-lambda│
│  • DABs version check (check_versions.sh)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  FASE 2 — BUILD (paralela)                                  │
│  • Docker RC image → ECR                                    │
│  • Lambda artifacts (zip)                                   │
│  • DABs validate (bundle validate)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  FASE 3 — HML DEPLOY (sequencial)                           │
│  • Provisionar ambiente efêmero HML                         │
│  • Deploy streaming (5 containers ECS HML)                  │
│  • Deploy DABs → HML workspace                              │
│  • Deploy Lambda → HML                                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  FASE 4 — HML TEST (paralela)                               │
│  • Teste streaming (hml_integration_test.sh)                │
│  • Teste DABs (hml_dlt_integration_test.sh)                 │
│  • Teste Lambda                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  FASE 5 — HML TEARDOWN (sempre executa)                     │
│  • Remove cluster ECS HML, security group, task definitions  │
└──────────────────────────┬──────────────────────────────────┘
                           │ (somente se TODOS os testes HML passaram)
┌──────────────────────────▼──────────────────────────────────┐
│  FASE 6 — CHECK PRD INFRA                                   │
│  • Valida ECS cluster / ECR                                 │
│  • Valida workspace Databricks (URL alcançável)              │
│  • Valida IAM roles Lambda                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  FASE 7 — PRD DEPLOY (sequencial)  ← GATE DE APROVAÇÃO      │
│  a. Streaming — promove RC → release, atualiza ECS           │
│  b. DABs      — bundle deploy --target prod                 │
│  c. Lambda    — terraform apply                              │
│  d. Tags      — v{VER}, v{VER}-dabs, v{VER}-lambda          │
└─────────────────────────────────────────────────────────────┘
```

### Jobs do Workflow (15 jobs)

| Job | Fase | Depende de |
|-----|------|-----------|
| `branch-guard` | CHECK | — |
| `all-check-version` | CHECK | branch-guard |
| `all-dabs-version-check` | CHECK | branch-guard |
| `all-stream-build-rc` | BUILD | all-check-version |
| `all-lambda-build` | BUILD | all-check-version |
| `all-dabs-bundle-validate` | BUILD | all-check-version |
| `all-hml-provision` | HML DEPLOY | todos builds |
| `all-hml-deploy-streaming` | HML DEPLOY | all-hml-provision |
| `all-hml-deploy-dabs` | HML DEPLOY | all-hml-provision |
| `all-hml-deploy-lambda` | HML DEPLOY | all-hml-provision |
| `all-hml-test-streaming` | HML TEST | all-hml-deploy-streaming |
| `all-hml-test-dabs` | HML TEST | all-hml-deploy-dabs |
| `all-hml-test-lambda` | HML TEST | all-hml-deploy-lambda |
| `all-hml-teardown` | HML TEARDOWN | `always()` |
| `all-check-infra` | CHECK PRD INFRA | todos HML tests |
| `all-prod-stream-deploy` | PRD DEPLOY | all-check-infra ← **GATE** |
| `all-prod-dabs-deploy` | PRD DEPLOY | all-prod-stream-deploy |
| `all-prod-lambda-deploy` | PRD DEPLOY | all-prod-stream-deploy |
| `all-prod-tag` | PRD TAGS | todos os PRD deploys |

---

## 2. Gate de Aprovação PRD

### Implementação Atual

O job `all-prod-stream-deploy` (linha 744 do workflow) já declara:

```yaml
environment: production
```

Isso ativa o mecanismo nativo de aprovação do GitHub Actions — quando um aprovador é configurado no GitHub Environment, o runner pausa antes de executar o job e aguarda aprovação manual.

### Status: Gate declarado, mas não configurado

A declaração `environment: production` existe no código. O que falta é a configuração no GitHub:

**Passos manuais obrigatórios:**
1. `GitHub → Settings → Environments`
2. Criar (ou editar) o ambiente `production`
3. Em **Required reviewers**, adicionar: `@marcoaurelioreislima` (ou o GitHub user responsável)
4. Opcionalmente: ativar **Wait timer** (ex.: 5 min) como buffer
5. Opcionalmente: restringir a branch `develop` como única branch autorizada

> **Referência:** `deploy_all_dm_applications.yml` linha 744

---

## 3. Lógica de Skip de Deploy DABs

O script `apps/dabs/check_versions.sh` avalia cada componente DABs contra git tags no padrão `dabs/{bundle-name}-v{VERSION}`.

### Exit codes do check_versions.sh

| Exit Code | Significado | Ação no CI |
|-----------|-------------|-----------|
| `0` | ≥1 componente com mudanças | Prossegue com deploy DABs |
| `1` | VERSION file ausente | **Falha** — pipeline bloqueado |
| `2` | Todos já deployados | Pula jobs DABs (`has_changes == 'false'`) |

### Como funciona o skip individual

O `deploy_all.sh` verifica tag `dabs/{bundle-name}-v{VERSION}` para cada componente:
- Tag existe → skip
- Tag ausente → deploy

Após deploy PRD bem-sucedido, `deploy_all.sh --tag` cria as tags para cada componente deployado.

---

## 4. Inventário de Componentes DABs (15 total)

| # | Diretório | Bundle Name | Tipo | VERSION | Tag PRD | Status |
|---|-----------|-------------|------|---------|---------|--------|
| 1 | `dlt_ethereum` | `dlt-ethereum` | DLT | 1.0.0 | `dabs/dlt-ethereum-v1.0.0` | ✅ |
| 2 | `dlt_app_logs` | `dlt-app-logs` | DLT | 1.0.0 | `dabs/dlt-app-logs-v1.0.0` | ✅ |
| 3 | `job_ddl_setup` | `job-ddl-setup` | Job | 1.0.0 | `dabs/job-ddl-setup-v1.0.0` | ✅ |
| 4 | `job_delta_maintenance` | `job-delta-maintenance` | Job | 1.0.0 | `dabs/job-delta-maintenance-v1.0.0` | ✅ |
| 5 | `job_export_gold` | `job-export-gold` | Job | 1.0.0 | `dabs/job-export-gold-v1.0.0` | ✅ |
| 6 | `job_full_refresh` | `job-full-refresh` | Job | 1.0.0 | `dabs/job-full-refresh-v1.0.0` | ✅ |
| 7 | `job_reconcile_orphans` | `job-reconcile-orphans` | Job | **AUSENTE** | — | ❌ **BLOQUEANTE** |
| 8 | `job_trigger_all` | `job-trigger-all` | Job | 1.0.0 | `dabs/job-trigger-all-v1.0.0` | ✅ |
| 9 | `alert_api_keys` | `alert-api-keys` | Alert | 1.0.0 | `dabs/alert-api-keys-v1.0.0` | ✅ |
| 10 | `alert_dynamodb_deadlock` | `alert-dynamodb-deadlock` | Alert | 1.0.0 | `dabs/alert-dynamodb-deadlock-v1.0.0` | ✅ |
| 11 | `dashboard_api_health` | `dashboard-api-health` | Dashboard | 1.0.0 | `dabs/dashboard-api-health-v1.0.0` | ✅ |
| 12 | `dashboard_gas_analytics` | `dashboard-gas-analytics` | Dashboard | 1.0.0 | `dabs/dashboard-gas-analytics-v1.0.0` | ✅ |
| 13 | `dashboard_hot_contracts` | `dashboard-hot-contracts` | Dashboard | 1.0.0 | `dabs/dashboard-hot-contracts-v1.0.0` | ✅ |
| 14 | `dashboard_network_overview` | `dashboard-network-overview` | Dashboard | 1.0.0 | `dabs/dashboard-network-overview-v1.0.0` | ✅ |
| 15 | `genie_ethereum` | `genie-ethereum` | Genie | 1.0.0 | `dabs/genie-ethereum-v1.0.0` | ✅ |

**Alertas/Dashboards/Genie (7 componentes)** requerem `warehouse_id` configurado no Databricks PRD.

---

## 5. Pré-requisitos de Infra PRD

### 5.1 Streaming (ECS + ECR)

| Item | Recurso TF | Status esperado |
|------|-----------|----------------|
| ECS Cluster | `services/prd/07_ecs/ecs.tf` | `ACTIVE` |
| 5 ECS Services | `dm-mined-blocks-watcher`, `dm-orphan-blocks-watcher`, `dm-block-data-crawler`, `dm-mined-txs-crawler`, `dm-txs-input-decoder` | Rodando |
| ECR repo | `onchain-stream-txs` | Existente |
| SSM — Alchemy keys | `/web3-api-keys/alchemy/api-key-1` e `api-key-2` | **Verificar manualmente** |
| SSM — Infura keys | `/web3-api-keys/infura/api-key-1-17` | **Verificar manualmente** |

### 5.2 Lambda

| Item | Recurso TF | Status esperado |
|------|-----------|----------------|
| IAM role contracts_ingestion | `dm-dd-chain-explorer-prd-contracts-ingestion-lambda` | Existente |
| IAM role gold_to_dynamodb | `dm-dd-chain-explorer-prd-gold-to-dynamodb-lambda` | Existente |
| EventBridge Scheduler (horário) | `aws_scheduler_schedule.contracts_ingestion_hourly` | ✅ Em TF |
| S3 trigger gold exports | `aws_s3_bucket_notification.gold_export` (prefix `exports/gold_api_keys/`) | ✅ Em TF |
| SSM — Etherscan API keys | `/etherscan-api-keys` | **Verificar manualmente** |

### 5.3 DABs (Databricks)

| Item | Fonte | Status esperado |
|------|-------|----------------|
| Workspace URL | TF output de `prd/05a_databricks_account` | Acessível (HTTP 200) |
| SQL Warehouse | UI Databricks PRD | **Verificar manualmente** — `warehouse_id` necessário para 7 componentes |
| OAuth M2M (client_id/secret) | GitHub Secrets | Configurado |
| Unity Catalog `dd_chain_explorer` | Databricks PRD | Existente |
| Schemas bronze/silver/gold | `job_ddl_setup` cria na primeira execução | — |

---

## 6. Problemas Identificados

| ID | Severidade | Componente | Problema | Impacto |
|----|-----------|-----------|---------|--------|
| **P-01** | 🔴 BLOQUEANTE | DABs | `job_reconcile_orphans/VERSION` ausente → `check_versions.sh` exit 1 | Pipeline DABs não inicia |
| **P-02** | 🔴 BLOQUEANTE | GitHub | Environment `production` sem Required Reviewers configurado | Gate de aprovação não funciona |
| **P-03** | 🟠 ALTO | CI Script | `check_infra_prerequisites.sh`: path TF state errado para DABs | Validação de pré-requisito pode falhar falsamente |
| **P-04** | 🟠 ALTO | PRD Infra | SSM parameters (Alchemy, Infura, Etherscan) — existência não confirmada | Apps falham em runtime sem as keys |
| **P-05** | 🟠 ALTO | DABs | SQL Warehouse em PRD não confirmado | 7 componentes (dashboards, alerts, genie) falham sem warehouse_id |
| **P-06** | 🟡 MÉDIO | CI Script | TF state path para DABs tem 2 fallbacks errados antes do correto via env var | Logs enganosos; atraso no diagnóstico |
| **P-07** | 🟡 MÉDIO | DABs | Componentes observabilidade (dashboards, alerts, genie) requerem `warehouse_id` como input manual | Deploy CI não consegue auto-resolver warehouse_id |

---

## 7. TODOs — Sequenciados e Priorizados

### Pré-Deploy (obrigatório antes do 1º deploy)

#### TODO-D01 — Criar `job_reconcile_orphans/VERSION` `[BLOQUEANTE]`

**Arquivo:** `apps/dabs/job_reconcile_orphans/VERSION`
**Conteúdo:** `1.0.0`
**Por quê:** `check_versions.sh` faz `exit 1` se qualquer componente com `databricks.yml` não tiver `VERSION` → bloqueia todo o pipeline DABs.

---

#### TODO-D02 — Configurar GitHub Environment `production` `[BLOQUEANTE — manual]`

**Passos:**
1. `GitHub → Settings → Environments → New environment` → nome: `production`
2. **Required reviewers** → adicionar o usuário responsável
3. Opcional: Wait timer 5 min
4. Opcional: restringir a branch `develop`

**Por quê:** Sem isso, o workflow pula a aprovação e vai direto para PRD deploy.

---

#### TODO-D03 — Validar pré-requisitos de infra PRD `[BLOQUEANTE — manual]`

Verificar antes do primeiro deploy:
- [ ] SSM: `/web3-api-keys/alchemy/api-key-1` e `api-key-2` existem em `sa-east-1`
- [ ] SSM: `/web3-api-keys/infura/api-key-1-17` existe
- [ ] SSM: `/etherscan-api-keys` existe
- [ ] SQL Warehouse existe no Databricks PRD; anotar o `warehouse_id`
- [ ] Variável `warehouse_id` configurada em cada bundle que precisar (ou `databricks.yml` de prod target override)
- [ ] ECS Cluster `dm-chain-explorer-ecs` está `ACTIVE`
- [ ] ECR repo `onchain-stream-txs` existe

---

#### TODO-D04 — Corrigir path TF state em `check_infra_prerequisites.sh` `[ALTO]`

**Arquivo:** `scripts/ci/check_infra_prerequisites.sh`

O script tenta ler o workspace URL do estado Terraform. Os dois primeiros caminhos são errados:

| Path no script | Existe? |
|---------------|---------|
| `prd/databricks/terraform.tfstate` | ❌ Não existe |
| `prd/databricks-workspace/terraform.tfstate` | ❌ Não existe |
| (fallback: `DATABRICKS_PROD_HOST` env var) | ✅ Funciona se configurado |

**Caminho correto:** `prd/databricks-account/terraform.tfstate`
(key configurada em `services/prd/05a_databricks_account/main.tf` linha 17)

**Fix:** Substituir o primeiro `aws s3 cp` por:
```bash
WS_URL=$(aws s3 cp "s3://${TF_STATE_BUCKET}/prd/databricks-account/terraform.tfstate" - 2>/dev/null \
  | jq -r '.outputs.databricks_workspace_url.value // empty') || WS_URL=""
```
Remover o segundo fallback (path igualmente errado).

---

### Configuração Opcional (melhora robustez)

#### TODO-D05 — Documentar `warehouse_id` na configuração dos bundles

**Arquivo:** `apps/dabs/databricks.yml` ou YAMLs dos bundles individuais

Os 7 componentes de observabilidade (`dashboard_*`, `alert_*`, `genie_ethereum`) requerem `warehouse_id` no target `prod`.
Confirmar que `databricks.yml` de cada um tem o valor correto no target `prod` (ou que o CI resolve via API).

**Não é bloqueante** se o bundle fazer `databricks bundle deploy` sem usar warehouse na validação — apenas as execuções de jobs/dashboards falharão.

---

#### TODO-D06 — Avaliar workflow CI: `check_infra_prerequisites.sh` para DABs

Após o fix do TODO-D04, executar o workflow e confirmar que a seção `databricks-dabs` de `check_infra_prerequisites.sh` passa com o URL correto lido do TF state.

---

### Segundo Deploy (validação)

#### TODO-D07 — Bump de versão para segundo deploy `[OBRIGATÓRIO para validar]`

Após o primeiro deploy validado, incrementar **todas** as versões `1.0.0 → 1.0.1`:

**Arquivo raiz:**
- `VERSION`: `1.0.0` → `1.0.1`

**Todos os 15 `apps/dabs/*/VERSION`:**
- `dlt_ethereum/VERSION`, `dlt_app_logs/VERSION`
- `job_ddl_setup/VERSION`, `job_delta_maintenance/VERSION`, `job_export_gold/VERSION`
- `job_full_refresh/VERSION`, `job_reconcile_orphans/VERSION` (novo, valor `1.0.0` → criar e já definir `1.0.1`)
- `job_trigger_all/VERSION`
- `alert_api_keys/VERSION`, `alert_dynamodb_deadlock/VERSION`
- `dashboard_api_health/VERSION`, `dashboard_gas_analytics/VERSION`
- `dashboard_hot_contracts/VERSION`, `dashboard_network_overview/VERSION`
- `genie_ethereum/VERSION`

---

#### TODO-D08 — Adicionar `GITHUB_STEP_SUMMARY` ao job de DABs `[MÉDIO]`

O job `all-prod-dabs-deploy` não publica resumo no Step Summary do GitHub Actions.
Adicionar ao final do script de deploy:
```bash
echo "## DABs Deploy — PRD" >> $GITHUB_STEP_SUMMARY
echo "Componentes deployados: ${DEPLOYED_COUNT}" >> $GITHUB_STEP_SUMMARY
```

---

#### TODO-D09 — Paralelizar deploys DABs independentes `[BAIXO]`

DLT pipelines, alerts, dashboards e genie podem ser deployados em paralelo (sem dependência entre si).
Apenas `job_trigger_all` depende dos IDs dos DLT pipelines.

Considerar refatorar `deploy_all.sh` para aceitar parâmetros de grupo e executar grupos em paralelo no CI.

---

## 8. Sequência de Validação — 2 Deploys Consecutivos

> **Critério de aceite:** 2 deploys completos (streaming + DABs + Lambda) de versões distintas, sem erros em nenhuma fase.

### Deploy 1 — Versão 1.0.0

**Pré-condições:**
- TODOs D01, D02, D03 completados
- Infra PRD provisionada (`Deploy Infra Cloud` executado com sucesso)

**Mudança mínima:**
- `VERSION` = `1.0.0` (já está — sem necessidade de alteração)
- Todos os 15 `apps/dabs/*/VERSION` = `1.0.0`

**Passos:**
1. Fazer commit na branch `develop`
2. Disparar `Deploy All DM Applications` (workflow_dispatch)
3. Aguardar fases CHECK → BUILD → HML DEPLOY → HML TEST → HML TEARDOWN → CHECK PRD INFRA
4. **Aprovar** o gate de produção no GitHub Actions (environment `production`)
5. Aguardar PRD DEPLOY (streaming → DABs → Lambda → tags)

**Critério de sucesso Deploy 1:**
- [ ] Todos os jobs de HML TEST passam (streaming + DABs + Lambda)
- [ ] Check PRD infra passa (ECS ACTIVE, workspace alcançável, IAM roles existentes)
- [ ] Deploy streaming completa + ECS services stable
- [ ] Deploy DABs completa (todos os 15 componentes ou apenas os não-taggeados)
- [ ] Deploy Lambda completa (terraform apply sem erro)
- [ ] Tags criadas: `v1.0.0`, `v1.0.0-dabs`, `v1.0.0-lambda`

---

### Deploy 2 — Versão 1.0.1 (validação final)

**Mudança mínima (TODO-D07):**
- Incrementar `VERSION`: `1.0.1`
- Incrementar todos os 15 `apps/dabs/*/VERSION`: `1.0.1`
- Commit: `chore(deps): bump version to 1.0.1 for deploy validation`

**Critério de sucesso Deploy 2:**
- [ ] `all-check-version` confirma que `v1.0.1`, `v1.0.1-dabs`, `v1.0.1-lambda` não existem
- [ ] `all-dabs-version-check` confirma `has_changes == 'true'` (todos 15 aparecem como DEPLOY)
- [ ] Todos os jobs de HML TEST passam novamente
- [ ] Gate de PRD ativado novamente (segunda aprovação manual)
- [ ] Deploy streaming: ECS services stable (task definitions atualizadas para v1.0.1)
- [ ] Deploy DABs: todos os 15 componentes deployados (tags `dabs/*-v1.0.1` criadas)
- [ ] Deploy Lambda: terraform apply (nova hash do zip → atualiza função)
- [ ] Tags criadas: `v1.0.1`, `v1.0.1-dabs`, `v1.0.1-lambda`

**Validação pós-deploy 2:**
- [ ] ECS: 5 serviços mostrando imagem tag `{git-sha}` correspondente ao commit
- [ ] Databricks PRD: pipelines DLT `dm-ethereum` e `dm-app-logs` com status Running/Scheduled
- [ ] Lambda `contracts_ingestion`: invocada na próxima hora (EventBridge Scheduler)
- [ ] Lambda `gold_to_dynamodb`: invocada após próximo export Gold (S3 trigger)

---

## 9. Referências de Arquivos

| Escopo | Caminho |
|--------|---------|
| Workflow principal | `.github/workflows/deploy_all_dm_applications.yml` |
| Check versão DABs | `apps/dabs/check_versions.sh` |
| Deploy DABs | `apps/dabs/deploy_all.sh` |
| Pré-requisitos PRD | `scripts/ci/check_infra_prerequisites.sh` |
| ECS PRD (5 services) | `services/prd/07_ecs/ecs.tf` |
| Lambda PRD | `services/prd/06_lambda/lambda.tf` |
| Lambda Contracts | `services/prd/06_lambda/lambda_contracts_ingestion.tf` |
| TF state key DABs | `services/prd/05a_databricks_account/main.tf` (linha 17) |
| Checklist deploy | `apps/dabs/DEPLOYMENT_CHECKLIST.md` |
| Guia de deploy | `apps/dabs/DEPLOYMENT_GUIDE.md` |
