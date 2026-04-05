# Relatório de Validação CI/CD — Infra-Estrutura

> **Data**: Abril 2026
> **Status**: Fase 0 — Implementação de pré-requisitos
> **Objetivo**: Validar a resiliência do pipeline de CI/CD de infra-estrutura através de ciclos completos de destroy → deploy → destroy → deploy em todos os ambientes (DEV, HML, PRD).

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Gaps Identificados](#2-gaps-identificados)
3. [Fase 0 — Pré-Requisitos](#3-fase-0--pré-requisitos)
4. [Fase 1 — Destroy Padrão (S3 Preservado)](#4-fase-1--destroy-padrão-s3-preservado)
5. [Fase 2 — Deploy do Zero](#5-fase-2--deploy-do-zero)
6. [Fase 3 — Re-Destroy (Idempotência)](#6-fase-3--re-destroy-idempotência)
7. [Fase 4 — Deploy Final (Validação de Resiliência)](#7-fase-4--deploy-final-validação-de-resiliência)
8. [Fase 5 — Nuclear Option Test (Diferido)](#8-fase-5--nuclear-option-test-diferido)
9. [Checklist de Verificação](#9-checklist-de-verificação)
10. [Log de Execução](#10-log-de-execução)

---

## 1. Visão Geral

### Objetivos

1. **Validar create/destroy idempotência** — todos os módulos Terraform devem ser criados e destruídos de forma reprodutível via CI/CD
2. **Testar a "nuclear option"** (`destroy_all_cloud_infra.yml`) — garantir que existe um mecanismo seguro para zero-cost teardown completo
3. **Identificar e registrar falhas** — qualquer erro no pipeline é documentado em `report-deploy-ci-cd.md` para análise e correção
4. **Preparar para pausa de 2 meses** — validar que a infra pode ser recriada sem dívida técnica após um período sem uso

### Ambientes Envolvidos

| Ambiente | Módulos TF | Comportamento S3 |
|----------|-----------|-----------------|
| **DEV** | `01_peripherals`, `02_lambda` | S3 preservado (standard destroy) |
| **HML** | `02_vpc`, `03_iam`, `04_peripherals`, `05_databricks`, `07_ecs` | S3 preservado (standard destroy + full_destroy) |
| **PRD** | `02_vpc`, `03_iam`, `04_peripherals`, `05a_databricks_account`, `05b_databricks_workspace`, `06_lambda`, `07_ecs` | S3 preservado (standard destroy) |
| **Bootstrap** | `01_tf_state` | Fase 5 apenas (nuclear) |

### Workflows Testados

| Workflow | Fases | Propósito |
|----------|-------|-----------|
| `deploy_cloud_infra.yml` | 2, 4 | Deploy por ambiente |
| `destroy_cloud_infra.yml` | 1, 3 | Destroy padrão (S3 preservado) |
| `destroy_all_cloud_infra.yml` | 5 | Nuclear destroy (tudo + S3 + tf_state) |

### Estado dos Módulos Terraform

| Módulo | State Key S3 | Tipo |
|--------|--------------|------|
| `prd/01_tf_state` | *(local — git)* | ⚠️ LOCAL (bootstrap) |
| `dev/01_peripherals` | `dev/peripherals/terraform.tfstate` | Remoto S3 |
| `dev/02_lambda` | `dev/lambda/terraform.tfstate` | Remoto S3 |
| `hml/02_vpc` | `hml/vpc/terraform.tfstate` | Remoto S3 |
| `hml/03_iam` | `hml/iam/terraform.tfstate` | Remoto S3 |
| `hml/04_peripherals` | `hml/peripherals/terraform.tfstate` | Remoto S3 |
| `hml/05_databricks` | `hml/databricks/terraform.tfstate` | Remoto S3 |
| `hml/07_ecs` | `hml/ecs/terraform.tfstate` | Remoto S3 |
| `prd/02_vpc` | `prd/vpc/terraform.tfstate` | Remoto S3 |
| `prd/03_iam` | `prd/iam/terraform.tfstate` | Remoto S3 |
| `prd/04_peripherals` | `prd/peripherals/terraform.tfstate` | Remoto S3 |
| `prd/05a_databricks_account` | `prd/databricks-account/terraform.tfstate` | Remoto S3 |
| `prd/05b_databricks_workspace` | `prd/databricks-workspace/terraform.tfstate` | Remoto S3 |
| `prd/06_lambda` | `prd/lambda/terraform.tfstate` | Remoto S3 |
| `prd/07_ecs` | `prd/ecs/terraform.tfstate` | Remoto S3 |

---

## 2. Gaps Identificados

Antes de iniciar os testes, foram identificados 3 gaps que impactavam a completude da validação:

### Gap 1 — HML Databricks sem caminho de deploy no CI/CD

| Campo | Detalhes |
|-------|----------|
| **Severidade** | 🔴 Bloqueante |
| **Arquivo** | `.github/workflows/deploy_cloud_infra.yml` |
| **Descrição** | `destroy_cloud_infra.yml` tem `hml-destroy-databricks`, mas `deploy_cloud_infra.yml` não tem nenhum job `hml-deploy-databricks`. Após destruir HML Databricks via CI/CD, o recurso não pode ser recriado pelo mesmo pipeline. |
| **Correção** | Adicionado job `hml-deploy-databricks` em `deploy_cloud_infra.yml` (Fase 0.1) |

### Gap 2 — Destroy padrão HML destrói apenas Databricks

| Campo | Detalhes |
|-------|----------|
| **Severidade** | 🟠 Limitante |
| **Arquivo** | `.github/workflows/destroy_cloud_infra.yml` |
| **Descrição** | Por design, `destroy_cloud_infra.yml` para HML destrói apenas `05_databricks`. Impossível testar destroy/redeploy completo do HML via CI/CD padrão. |
| **Correção** | Adicionado input `full_destroy` (boolean, default false) + jobs condicionais: `hml-destroy-ecs`, `hml-destroy-peripherals`, `hml-destroy-iam`, `hml-destroy-vpc` (Fase 0.2) |

### Gap 3 — `hml-destroy-databricks` sem `if` de ambiente

| Campo | Detalhes |
|-------|----------|
| **Severidade** | 🟠 Bug |
| **Arquivo** | `.github/workflows/destroy_cloud_infra.yml` |
| **Descrição** | O job `hml-destroy-databricks` não tinha `if: github.event.inputs.environment == 'hml'`, resultando em execução para qualquer valor de `environment` (DEV, HML, PRD). |
| **Correção** | `if:` adicionado ao job (Fase 0.2) |

---

## 3. Fase 0 — Pré-Requisitos

### 3.1 — Adições ao `deploy_cloud_infra.yml`

Adicionado job `hml-deploy-databricks`:
- **Needs**: `hml-deploy-iam` (Databricks precisa de IAM para cross-account trust)
- **Paralelo com**: `hml-deploy-ecs` (ambos dependem apenas de IAM)
- **Env vars**: `DATABRICKS_ACCOUNT_ID`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`
- **Concurrency group**: `tf-hml-databricks`
- **`terraform_wrapper: false`**: habilitado (evita parsing incorreto de output)

### 3.2 — Adições ao `destroy_cloud_infra.yml`

1. **Novo input** `full_destroy` (boolean, default `false`, HML only):
   - `false` (default): comportamento atual — destrói apenas Databricks
   - `true`: destrói tudo (Databricks + ECS → Peripherals S3-preserved → IAM → VPC com ENI wait)

2. **Correção** `if: github.event.inputs.environment == 'hml'` em `hml-destroy-databricks`

3. **Novos jobs** (condicionais a `full_destroy == 'true'`):
   - `hml-destroy-ecs` — paralelo com `hml-destroy-databricks` (ambos `needs: safety-check`)
   - `hml-destroy-peripherals` — após Databricks+ECS, S3 preservado via `-target=module.dynamodb -target=module.kinesis -target=module.sqs -target=module.cloudwatch_logs`
   - `hml-destroy-iam` — após Peripherals
   - `hml-destroy-vpc` — após IAM, com `wait_eni_release.sh` (`VPC_NAME_TAG: dm-chain-explorer-hml`)

4. **`hml-summary`** atualizado para `needs: [hml-destroy-databricks, hml-destroy-vpc]` — funciona em ambos os modos (vpc é skipped quando `full_destroy=false`, o `if: always()` garante que summary sempre executa)

### 3.3 — Fixes P0 já aplicados

| Issue | Status |
|-------|--------|
| IS-02: `prevent_destroy=false` no tf_state | ✅ Corrigido (sessão anterior) |
| IS-03: Sem concurrency groups | ✅ Presente nos workflows atuais |
| IS-06: IAM dependency incorreta no PRD deploy | ✅ Corrigido |

### 3.4 — Issues Diferidos

| Issue | Motivo do Defer |
|-------|----------------|
| IS-01: `terraform.tfstate` no git | Requer `git filter-repo` + force push — não destabilizar durante o período de testes |
| IS-05: `tf_state_lock_check.sh` usa DynamoDB direto | Melhoria de segurança — melhor approach com `terraform force-unlock <ID>` |

---

## 4. Fase 1 — Destroy Padrão (S3 Preservado)

**Workflow**: `destroy_cloud_infra.yml`
**S3 preservado**: DEV (1), HML (3), PRD (3) + tf_state (1) = 8 buckets no total

### 4.1 Pré-flight Snapshot

Antes de qualquer destroy, registrar estado atual:
```bash
# Recurso count por módulo
for MODULE in services/prd/02_vpc services/prd/04_peripherals services/prd/03_iam \
              services/prd/05a_databricks_account services/prd/05b_databricks_workspace \
              services/prd/06_lambda services/prd/07_ecs \
              services/hml/02_vpc services/hml/03_iam services/hml/04_peripherals \
              services/hml/05_databricks services/hml/07_ecs \
              services/dev/01_peripherals services/dev/02_lambda; do
  COUNT=$(terraform -chdir="$MODULE" state list 2>/dev/null | wc -l)
  echo "$MODULE: $COUNT resources"
done

# Buckets S3
aws s3 ls | grep "dm-chain-explorer"
```

### 4.2 Sequência de Execução

**Ordem recomendada**: PRD → DEV → HML (maior risco primeiro, enquanto tudo está saudável)

| Passo | Workflow | Inputs | Sequence Detail |
|-------|----------|--------|-----------------|
| **1.1** | `destroy_cloud_infra.yml` | env=`prd`, confirm=`DESTROY` | Empty ECR → Lambda+ECS (paralelo) → Databricks ws (URL fallback API) → Databricks account (re-import) → Peripherals (`-target` S3 preserved) → IAM → VPC (ENI wait) |
| **1.2** | `destroy_cloud_infra.yml` | env=`DEV (Cloud AWS)`, confirm=`DESTROY` | Lambda → Peripherals (`-target` S3 preserved) |
| **1.3** | `destroy_cloud_infra.yml` | env=`hml`, confirm=`DESTROY`, full_destroy=`true` | Databricks+ECS (paralelo) → Peripherals (S3 preserved) → IAM → VPC (ENI wait `dm-chain-explorer-hml`) |

### 4.3 Verificação Pós-Destroy

- [ ] `terraform state list` retorna 0 recursos por módulo
- [ ] `aws s3 ls | grep dm-chain-explorer` = 8 buckets
- [ ] `aws dynamodb list-tables` inclui `dm-chain-explorer-terraform-lock`
- [ ] GitHub Actions: todos os runs com status `success`

---

## 5. Fase 2 — Deploy do Zero

**Workflow**: `deploy_cloud_infra.yml`
**Nota**: Usar `force_apply=true` em todos os deploys (tag `v{VERSION}-infra` já existe; `force_apply` bypassa a verificação de tag)

### 5.1 Sequência de Execução

| Passo | Workflow | Inputs | Sequence Detail |
|-------|----------|--------|-----------------|
| **2.1** | `deploy_cloud_infra.yml` | env=`prd`, force_apply=`true` | Version check (force skip) → VPC+Peripherals L1 (paralelo) → IAM L2 → Databricks account+Lambda+ECS L3 (paralelo) → Databricks workspace L4 → Tag git |
| **2.2** | `deploy_cloud_infra.yml` | env=`DEV (Cloud AWS)`, force_apply=`true` | Detect changes (force=true → ambos changed) → Peripherals → Lambda |
| **2.3** | `deploy_cloud_infra.yml` | env=`hml` | VPC+Peripherals L1 (paralelo) → IAM L2 → ECS+Databricks L3 (paralelo) |

### 5.2 Verificação Pós-Deploy

- [ ] Kinesis streams ativos: DEV (3 streams), PRD (3 streams)
- [ ] DynamoDB tables: DEV (1), PRD (1)
- [ ] ECS clusters: HML (1), PRD (1)
- [ ] VPC + subnets: HML, PRD
- [ ] Databricks workspaces acessíveis: HML, PRD
- [ ] `terraform state list` mostra recursos recriados (count = baseline do pré-flight)

---

## 6. Fase 3 — Re-Destroy (Idempotência)

**Propósito**: Provar que o destroy funciona de forma idempotente após um deploy completo do zero.

Idêntica à Fase 1. Qualquer diferença de comportamento (novos erros, timeouts, recursos extras) deve ser registrada em `report-deploy-ci-cd.md` com comparação ao comportamento da Fase 1.

---

## 7. Fase 4 — Deploy Final (Validação de Resiliência)

**Propósito**: Validar que a infra-estrutura é totalmente recreável após dois ciclos completos de destroy/deploy. Esta é a prova de resiliência.

Idêntica à Fase 2. Ao final desta fase, o projeto está em estado operacional pleno.

---

## 8. Fase 5 — Nuclear Option Test (Diferido)

**Propósito**: Testar `destroy_all_cloud_infra.yml` (scorched earth) + rebuild completo do absolute zero (sem tf_state).

> ⚠️ **ATENÇÃO**: Esta fase destrói **todos** os dados em **todos** os buckets S3 (raw, lakehouse, databricks, dev-ingestion, hml raw/lakehouse/databricks) + o próprio bucket de tf_state. **Dados dos buckets serão perdidos permanentemente.**
>
> Executar somente em sessão separada, após confirmar que não há dados a recuperar.

### 8.1 Nuclear Destroy
- **Workflow**: `destroy_all_cloud_infra.yml` → confirm=`DESTROY ALL`
- **Destrói**: DEV (lambda + peripherals incl. S3) + HML (tudo incl. S3) + PRD (tudo incl. S3) + tf_state bucket + DynamoDB lock
- **Resultado esperado**: Zero recursos AWS após conclusão (exceto IAM users de CI/CD)

### 8.2 Rebuild do Bootstrap

```bash
# Recriar o state bucket + DynamoDB lock
cd services/prd/01_tf_state
terraform init -reconfigure
terraform apply -auto-approve
```

Resultado: bucket `dm-chain-explorer-terraform-state` + tabela `dm-chain-explorer-terraform-lock` recriados.

### 8.3 Deploy Completo
Mesmo sequência da Fase 2 (PRD → DEV → HML).

---

## 9. Checklist de Verificação

### Por Destory (Fases 1, 3)

- [ ] `terraform state list` retorna 0 recursos por módulo (15 módulos remotos)
- [ ] `aws s3 ls | grep dm-chain-explorer` retorna 8 buckets (standard) ou 0 (nuclear)
- [ ] `aws dynamodb list-tables | grep dm-chain-explorer-terraform-lock` presente (standard) ou ausente (nuclear)
- [ ] GitHub Actions `destroy_cloud_infra.yml` todos os jobs `success`
- [ ] Nenhum lock órfão em `dm-chain-explorer-terraform-lock` (`aws dynamodb scan --table-name dm-chain-explorer-terraform-lock`)

### Por Deploy (Fases 2, 4)

- [ ] `terraform state list` mostra recursos recriados (count ≥ baseline pré-flight)
- [ ] `aws kinesis list-streams` — DEV: 3 streams, PRD: 3 streams
- [ ] `aws dynamodb list-tables` — DEV e PRD: 1 tabela cada
- [ ] `aws ecs list-clusters` — HML: 1, PRD: 1
- [ ] Databricks workspaces acessíveis via browser (HML URL, PRD URL)
- [ ] GitHub Actions `deploy_cloud_infra.yml` todos os jobs `success`

---

## 10. Log de Execução

> Erros detalhados e investigações em `report-deploy-ci-cd.md`.

| Fase | Data | GitHub Run # | Ambiente | Status | Notas |
|------|------|-------------|----------|--------|-------|
| 0 | 2026-04-05 | — | — | 🟡 Em andamento | Gap 1/2/3 corrigidos nos workflows |
| 1 | — | — | PRD | ⏳ Pendente | — |
| 1 | — | — | DEV | ⏳ Pendente | — |
| 1 | — | — | HML | ⏳ Pendente | — |
| 2 | — | — | PRD | ⏳ Pendente | — |
| 2 | — | — | DEV | ⏳ Pendente | — |
| 2 | — | — | HML | ⏳ Pendente | — |
| 3 | — | — | PRD | ⏳ Pendente | — |
| 3 | — | — | DEV | ⏳ Pendente | — |
| 3 | — | — | HML | ⏳ Pendente | — |
| 4 | — | — | PRD | ⏳ Pendente | — |
| 4 | — | — | DEV | ⏳ Pendente | — |
| 4 | — | — | HML | ⏳ Pendente | — |
| 5 | — | — | ALL | ⏳ Diferido | Nuclear option — executar em sessão separada |
