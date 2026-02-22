# Gitflow e Pipeline de CI/CD

## Visão Geral

O projeto utiliza uma estratégia de Gitflow simplificada com dois tipos de branches principais. O deploy de todos os componentes em produção é feito exclusivamente via GitHub Actions, com aprovação manual obrigatória para qualquer alteração em infraestrutura ou na plataforma Databricks.

---

## Estrutura de Branches

```
main
 └── branch de feature (feature/...) ou fix (fix/...)
```

| Branch | Propósito |
|--------|-----------|
| `main` | Produção. Todo merge aqui dispara o CI/CD correspondente. |
| `feature/*` | Desenvolvimento de novas funcionalidades. |
| `fix/*` | Correções de bugs. |

O fluxo padrão é:

```
feature/minha-feature → Pull Request → code review → merge em main → CI/CD dispara automaticamente
```

---

## Pipelines de CI/CD

Existem **três workflows independentes** em `.github/workflows/`, cada um responsável por um domínio diferente do projeto. Cada um é ativado por `push` em `main` dentro de um path específico, ou pode ser disparado manualmente via `workflow_dispatch`.

---

### 1. Deploy de Infraestrutura (`deploy_infrastructure.yml`)

**Arquivo:** `.github/workflows/deploy_infrastructure.yml`
**Trigger:** push em `main` com alterações em `dd_chain_explorer/terraform/**`

#### Fluxo

```
detect-changes → terraform-plan (por módulo) → [aprovação manual] → terraform-apply
```

#### Jobs

| Job | Descrição |
|-----|-----------|
| `detect-changes` | Detecta quais módulos Terraform foram alterados via `git diff`. Se `workflow_dispatch` especificar um módulo, usa o módulo informado. |
| `terraform-plan` | Roda `init → validate → plan` para cada módulo alterado em paralelo (matrix strategy). O plano é salvo como artefato. |
| `terraform-apply` | Faz download do artefato de plano e aplica. **Requer aprovação manual via environment `production`.** |

#### Módulos Terraform

Os módulos são numerados e devem ser aplicados na ordem de dependência:

```
0_remote_state → 1_vpc → 2_iam → 3_msk → 4_s3 → 5_dynamodb → 6_ecs → 7_databricks
```

#### Secrets necessários

| Secret | Uso |
|--------|-----|
| `AWS_ACCESS_KEY_ID` | Credenciais AWS para Terraform |
| `AWS_SECRET_ACCESS_KEY` | Credenciais AWS para Terraform |
| `DATABRICKS_ACCOUNT_ID` | Criação do workspace Databricks (módulo 7) |
| `DATABRICKS_CLIENT_ID` | Service principal Databricks |
| `DATABRICKS_CLIENT_SECRET` | Service principal Databricks |

---

### 2. Deploy dos DABs — Databricks Asset Bundles (`deploy_databricks.yml`)

**Arquivo:** `.github/workflows/deploy_databricks.yml`
**Trigger:** push em `main` com alterações em `dd_chain_explorer/dabs/**`

#### Fluxo

```
validate (bundle validate) → [aprovação manual] → deploy-prod (bundle deploy --target prod)
```

#### Jobs

| Job | Descrição |
|-----|-----------|
| `validate` | Executa `databricks bundle validate --target prod`. |
| `deploy-prod` | Executa `databricks bundle deploy --target prod` com todas as variáveis injetadas via secrets. **Requer aprovação manual via environment `production`.** |

Após o deploy, o job verifica os recursos criados listando pipelines DLT e workflows.

#### Variáveis injetadas via `--var`

| Variável | Secret correspondente |
|----------|----------------------|
| `prod_workspace_host` | `DATABRICKS_PROD_HOST` |
| `kafka_bootstrap_servers` | `MSK_BOOTSTRAP_SERVERS` |
| `dynamodb_semaphore_table` | `DYNAMODB_SEMAPHORE_TABLE` |
| `dynamodb_consumption_table` | `DYNAMODB_CONSUMPTION_TABLE` |
| `dynamodb_popular_contracts_table` | `DYNAMODB_POPULAR_CONTRACTS_TABLE` |

#### Secrets necessários

| Secret | Uso |
|--------|-----|
| `DATABRICKS_PROD_HOST` | URL do workspace Databricks em PROD |
| `DATABRICKS_PROD_TOKEN` | Token de acesso ao workspace |
| `MSK_BOOTSTRAP_SERVERS` | Endereços dos brokers MSK |

---

### 3. Deploy das Aplicações Docker → ECS (`deploy_apps.yml`)

**Arquivo:** `.github/workflows/deploy_apps.yml`
**Trigger:** push em `main` com alterações em:
- `dd_chain_explorer/docker/app_layer/onchain-stream-txs/**`
- `dd_chain_explorer/docker/app_layer/onchain-batch-txs/**`
- `lib-dm-utils/**`

#### Fluxo

```
detect-changes → build-push-stream (condicional) + build-push-batch (condicional) → update ECS services
```

#### Jobs

| Job | Condição | Descrição |
|-----|----------|-----------|
| `detect-changes` | sempre | Detecta se `onchain-stream-txs` ou `onchain-batch-txs` mudaram (ou `lib-dm-utils`). |
| `build-push-stream` | se stream mudou | Build da imagem `onchain-stream-txs`, tag com git short SHA + `latest`, push para DockerHub. |
| `build-push-batch` | se batch mudou | Build da imagem `onchain-batch-txs`, tag com git short SHA + `latest`, push para DockerHub. |

Após o push da imagem, o workflow:
1. Descreve a task definition atual via AWS CLI
2. Registra uma nova task definition com a nova imagem
3. Faz `update-service` em cada serviço ECS afetado

#### Serviços ECS atualizados (stream)

- `dm-mined-blocks-watcher`
- `dm-orphan-blocks-watcher`
- `dm-block-data-crawler`
- `dm-mined-txs-crawler`

#### Secrets necessários

| Secret | Uso |
|--------|-----|
| `DOCKERHUB_USERNAME` | Login DockerHub |
| `DOCKERHUB_TOKEN` | Token DockerHub |
| `AWS_ACCESS_KEY_ID` | Credenciais AWS para ECS |
| `AWS_SECRET_ACCESS_KEY` | Credenciais AWS para ECS |

---

## Deploy Manual (Desenvolvimento)

Para deploys em DEV sem passar pelo CI/CD, utilize os targets do Makefile:

```bash
# Validar e fazer deploy do bundle DABs em DEV
make dabs_validate
make dabs_deploy_dev

# Executar um workflow específico em DEV
make dabs_run_dev JOB=dm-ddl-setup

# Build e deploy local das aplicações Python
make deploy_dev_stream

# Ver status do bundle em DEV
make dabs_status_dev
```

Consulte o [ambiente de desenvolvimento](dev_environment.md) para detalhes completos sobre como subir a infraestrutura local antes de testar.

---

## Proteção do Branch `main`

Configurações recomendadas de branch protection no GitHub:

- **Require pull request reviews before merging:** 1 aprovação
- **Require status checks to pass:** os jobs de `validate` / `terraform-plan` devem passar
- **Require linear history:** rebase obrigatório
- **Environment `production`:** aprovação manual obrigatória antes dos jobs de apply/deploy
