# Spec: Domínio — Infrastructure

> **Status:** Implementado
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/architecture.md`, `specs/memory/aws-resources.md`, `specs/memory/constitution.md`

---

## Escopo

Toda a infraestrutura AWS gerenciada via Terraform:
- Módulos reutilizáveis em `services/modules/`
- Ambiente DEV (`services/dev/`)
- Ambiente HML (`services/hml/`)
- Ambiente PRD (`services/prd/`)

Este domínio NÃO inclui: código de aplicação, DABs Databricks, pipelines CI/CD.

---

## Princípios

**Terraform é a única fonte de verdade.** Nenhum recurso pode ser criado, modificado ou destruído via AWS Console ou CLI. Toda mudança começa em código `.tf`.

---

## Módulos Compartilhados (`services/modules/`)

| Módulo | Recursos provisionados |
|--------|----------------------|
| `s3` | Bucket (encryption AES256, versioning, block public, lifecycle rules) |
| `kinesis` | Data Streams PROVISIONED + Firehose → S3 com partição horária |
| `sqs` | Queues + Dead Letter Queues (max_receive configurable) |
| `dynamodb` | Single-table (pk + sk), TTL opt-in, PITR |
| `ecs` | Cluster, ECR, task definitions, service discovery |
| `lambda` | Functions, layers, S3 event triggers, EventBridge rules |
| `iam` | Roles e policies least-privilege por ambiente |
| `vpc` | VPC, subnets (public + private), IGW, SGs, S3 VPC endpoint |
| `cloudwatch_logs` | Log groups + Firehose subscription → S3 `raw/app_logs/` |

---

## Ambientes

### DEV (`services/dev/`)

| Módulo | State | Recursos principais |
|--------|-------|---------------------|
| `01_peripherals` | local | S3, DynamoDB, Kinesis, Firehose, SQS, CloudWatch |
| `02_lambda` | local | Lambda `gold-to-dynamodb-dev` |

- State local (gitignored) — nunca remoto
- Docker Compose sobe os 5 streaming jobs localmente: `services/dev/00_compose/app_services.yml`

### HML (`services/hml/`)

7 módulos com state S3 remoto. **100% efêmero** — criado e destruído dentro do mesmo CI run.

| Ordem | Módulo | Responsabilidade |
|-------|--------|-----------------|
| 1 | `01_tf_state_placeholder` | Reserva path de state (idempotente) |
| 2 | `02_vpc` | VPC HML |
| 3 | `03_iam` | Roles para ECS HML |
| 4 | `04_peripherals` | S3, Kinesis, SQS, DynamoDB HML |
| 5 | `05_databricks` | Databricks Free Edition HML |
| 5b | `05b_databricks_workspace` | Unity Catalog HML |
| 7 | `07_ecs` | ECS tasks HML (efêmeras) |

### PRD (`services/prd/`)

State S3 remoto com DynamoDB lock. Persistente. Deploy apenas via CI/CD com approval gate.

| Fase | Módulos | Dependência |
|------|---------|-------------|
| 1 | `01_tf_state` | — (bootstrap) |
| 2 | `02_vpc` + `04_peripherals` | `01_tf_state` |
| 3 | `03_iam` | `02_vpc` + `04_peripherals` |
| 4 | `05a_databricks_account` + `06_lambda` + `07_ecs` | `03_iam` |
| 5 | `05b_databricks_workspace` | `05a_databricks_account` |

**Destroy order:** inverso da deploy order. Nunca destruir `01_tf_state` (contém o state de tudo).

---

## Recursos AWS (PRD)

### Storage
| Bucket | Propósito | Lifecycle |
|--------|-----------|-----------|
| `dm-chain-explorer-raw-data` | S3 Bronze NDJSON via Firehose | 30d → IA, 90d → Glacier |
| `dm-chain-explorer-lakehouse` | Delta tables (Bronze/Silver/Gold) | 90d → IA |
| `dm-chain-explorer-databricks` | Databricks internal (checkpoints, staging, Unity Catalog) | Checkpoints: 365d expiry |

### Streaming
| Recurso | Configuração |
|---------|-------------|
| Kinesis `mainnet-transactions-data` | PROVISIONED, 1 shard, 24h retention |
| Firehose Direct Put (3 streams) | blocks-data, transactions-decoded, app-logs → S3 horário |

### Mensageria
| Fila | Visib. Timeout | DLQ | Max Receive |
|------|---------------|-----|-------------|
| `mainnet-mined-blocks-events` | 30s | Sim | 3 |
| `mainnet-block-txs-hash-id` | 60s | Sim | 3 |

### Compute
| Recurso | Detalhes |
|---------|----------|
| DynamoDB | Single-table `dm-chain-explorer`, PITR habilitado |
| ECS Fargate | 5 task definitions (1+1+1+6+3 replicas), ECR `onchain-stream-txs` |
| Lambda | `contracts_ingestion` (EventBridge hourly) + `gold_to_dynamodb` (S3 trigger) |
| VPC | 10.0.0.0/16, 1 public + 2 private subnets, sa-east-1 |

---

## Requisitos Funcionais

**FR-INF-001 — IaC exclusivo**
Nenhum recurso AWS pode ser criado fora do Terraform. Violação invalida o state rastreado.

**FR-INF-002 — Remote state PRD**
State PRD em `s3://dm-chain-explorer-terraform-state/{env}/{module}/terraform.tfstate` com lock `dm-chain-explorer-terraform-lock`.

**FR-INF-003 — Tags obrigatórias**
Todo recurso deve ter: `owner`, `managed-by`, `cost-center`, `environment`, `project`.

**FR-INF-004 — Naming**
Padrão: `dm-{env}-{tipo}` ou `dm-chain-explorer-{env}-{tipo}`. `env` = `dev` | `hml` | (vazio para PRD).

**FR-INF-005 — HML efêmero**
Módulos HML não devem ter recursos persistentes. Toda infraestrutura HML deve ser criável e destruível em um único CI run sem efeitos colaterais.

**FR-INF-006 — Ordem de deploy PRD**
A sequência de módulos em PRD deve ser respeitada rigorosamente. Scripts `deploy_env.sh` e o workflow `deploy_cloud_infra.yml` implementam essa ordem.

---

## Requisitos Não-Funcionais

- **NFR-INF-001:** Secrets nunca em arquivos `.tf` — via SSM Parameter Store em runtime ou GitHub Secrets no CI.
- **NFR-INF-002:** S3 buckets: todos os 4 block-public settings = `true`, AES256, versioning.
- **NFR-INF-003:** IAM: nunca `s3:*` ou `iam:*` — resources sempre scoped por ARN com sufixo de ambiente.
- **NFR-INF-004:** PRD apply apenas via CI/CD com approval gate `production`.
