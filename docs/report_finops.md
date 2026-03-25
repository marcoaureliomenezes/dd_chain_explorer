# 08 — Report FinOps

> **Gerado em:** 2026-03-24 | **Período:** 2026-03 (MTD) | **Região AWS:** sa-east-1
> **Gerado pelo workflow:** `/report-finops`

---

## 1. Inventário de Recursos por Ambiente

> **Status em 2026-03-24:** HML 100% provisionado via Terraform; PRD ECS cluster inativo (aguarda `deploy_cloud_infra prd`). DEV Kinesis streams ativos durante sprint de dev.

### DEV

| Recurso | Nome / Spec | Status | Custo Est. USD/mês |
|---------|-------------|--------|---------------------|
| Kinesis Streams (3) | `mainnet-blocks-data-dev`, `mainnet-transactions-data-dev`, `mainnet-transactions-decoded-dev` — ON_DEMAND | ✅ ACTIVE | **~$8–12/dia quando ativo** ⚠️ |
| Kinesis Firehose (4) | `firehose-mainnet-blocks-data-dev`, `*-transactions-data-dev`, `*-transactions-decoded-dev`, `firehose-app-logs-dev` | ✅ ACTIVE | ~$0.03 |
| SQS Queues (4) | `mainnet-mined-blocks-events-dev` + DLQ, `mainnet-block-txs-hash-id-dev` + DLQ | ✅ ACTIVE | ~$0.50 |
| S3 Bucket | `dm-chain-explorer-dev-ingestion` | ✅ ACTIVE | ~$0.08 |
| DynamoDB Table | `dm-chain-explorer-dev` — On-demand | ✅ ACTIVE | ~$0.10 |
| Lambda | `dm-chain-explorer-gold-to-dynamodb-dev` | ✅ ACTIVE | < $0.01 |
| ECR | `onchain-stream-txs` (account-level, shared DEV/PRD) | ✅ ACTIVE | ~$0.02 |
| ECS Cluster | `cluster-docker-on-prem` (DEV local compose, não Fargate AWS) | ✅ ACTIVE | $0 Fargate |
| **Total DEV (Kinesis ativo 24/7)** | | | **~$250–360** |
| **Total DEV (sem Kinesis permanente)** | | | **~$0.75** |

### HML

| Recurso | Nome / Spec | Status | Custo Est. USD/mês |
|---------|-------------|--------|---------------------|
| ECS Cluster | `dm-chain-explorer-ecs-hml` — Fargate | ✅ ACTIVE (idle pós-teardown) | ~$0.10/run CI (efêmero) |
| Kinesis Streams (3) | `mainnet-blocks-data-hml`, `mainnet-transactions-data-hml`, `mainnet-transactions-decoded-hml` — criados/destruídos por CI | ♻️ Efêmero (`terraform destroy` pós-run) | ~$0.05/run |
| Kinesis Firehose (1) | `firehose-app-logs-hml` | ✅ ACTIVE (persistente) | < $0.01 |
| SQS Queues (4) | `mainnet-mined-blocks-events-hml` + DLQ, `mainnet-block-txs-hash-id-hml` + DLQ | ✅ ACTIVE (persistente) | ~$0.01 |
| S3 Buckets (3) | `dm-chain-explorer-hml-raw`, `*-lakehouse`, `*-databricks` (lifecycle 7/30 dias) | ✅ ACTIVE | < $0.01 |
| DynamoDB Table | `dm-chain-explorer-hml` — On-demand | ✅ ACTIVE | < $0.01 |
| IAM Roles | ECS execution/task, firehose, Lambda (contracts_ingestion, gold_to_dynamodb) | ✅ ACTIVE | $0 |
| **Total HML (mensal)** | | | **< $0.50** |

### PRD

| Recurso | Nome / Spec | Status | Custo Est. USD/mês |
|---------|-------------|--------|---------------------|
| VPC + Subnets + NAT | VPC dedicada + NAT Gateway + Elastic IP | ✅ ACTIVE | ~$2.07 |
| ECS Cluster | `dm-chain-explorer-ecs` | ❌ INACTIVE (aguarda `deploy_cloud_infra prd`) | — |
| S3 `dm-chain-explorer-terraform-state` | TF backend | ✅ ACTIVE | < $0.01 |
| DynamoDB `dm-chain-explorer-terraform-lock` | TF lock | ✅ ACTIVE | < $0.01 |
| Route 53 | Hosted zone(s) | ✅ ACTIVE | ~$0.50 |
| ECR | `onchain-stream-txs`, `onchain-batch-txs` (shared com DEV) | ✅ ACTIVE | ~$0.02 |
| IAM Roles | ECS, Lambda, Firehose, Databricks cross-account | ✅ ACTIVE | $0 |
| S3 buckets raw/lakehouse/databricks | Aguardando `deploy_cloud_infra prd` | ❌ não criados | — |
| Kinesis Streams (3+) | Aguardando `deploy_cloud_infra prd` | ❌ não criados | — |
| SQS + Firehose + DynamoDB | Aguardando `deploy_cloud_infra prd` | ❌ não criados | — |
| ECS Fargate (5 serviços 24/7) | 0.25 vCPU / 0.5 GB cada | ❌ não ativo | ~$12–18 (estimativa) |
| **Total PRD atual** | | | **~$2.60** |
| **Total PRD alvo (pós-deploy completo)** | | | **~$37–52** |

---

## 2. Custo Real — AWS Cost Explorer (2026-03 MTD, conta completa)

> **Nota:** filtro por tag `project=dd-chain-explorer` retornou $0 — recursos DEV mais antigos não possuem a tag aplicada. Custo abaixo é da conta inteira. Ver Seção 5 para ação de correção.

| Serviço AWS | Custo USD (mar/26 MTD) | Observação |
|-------------|----------------------:|------------|
| Amazon Kinesis | $41.83 | ⚠️ DEV streams ON_DEMAND ativos Mar 19–23 (~$8/dia). Custo sprint de dev. |
| Amazon MSK / Kafka | $27.04 | ⚠️ Cluster MSK da arquitetura anterior destruído em Mar 18. Custo **one-time**. |
| Tax | $11.08 | Impostos sobre serviços |
| Amazon ECS (Fargate) | $2.99 | CI/CD HML runs + testes de infra ao longo do mês |
| Amazon VPC | $2.07 | NAT Gateway + Elastic IP — custo fixo |
| Amazon Route 53 | $2.00 | Hosted zones — custo fixo |
| Amazon S3 | $1.74 | Buckets de dados + TF state + logs |
| Amazon EC2 Compute | $0.81 | Instâncias build/teste |
| Amazon DynamoDB | $0.49 | Tabelas dev/hml + TF lock |
| EC2 - Other | $0.29 | EBS, snapshots |
| AWS Cost Explorer | $0.15 | API queries |
| Amazon Kinesis Firehose | $0.03 | Firehoses dev/hml |
| Amazon ECR | $0.02 | Armazenamento de imagens |
| AWS KMS | < $0.01 | Chaves de criptografia |
| **TOTAL** | **$90.55** | |

### Detalhamento Kinesis (diário)

| Data | Custo USD |
|------|----------:|
| 2026-03-19 | $8.96 |
| 2026-03-20 | $9.12 |
| 2026-03-21 | $7.19 |
| 2026-03-22 | $10.36 |
| 2026-03-23 | $6.19 |
| **Total Kinesis** | **$41.83** (5 dias de dev ativo) |

---

## 3. Tendência Mensal

| Mês | Total AWS (USD) | Top Driver | Observação |
|-----|---------------:|------------|------------|
| 2025-12 | $4.92 | VPC $3.72 | Baseline: apenas infra base (VPC + Route53 + S3 + ECR) |
| 2026-01 | $4.92 | VPC $3.72 | Idêntico — sem ECS/Kinesis ativos |
| 2026-02 | $12.42 | ECS $5.22 | Primeiro deploy ECS + MSK inicial ($0.77) |
| 2026-03 | $90.55 ⚠️ | Kinesis $41.83 + MSK $27.04 | Sprint dev ativo + MSK one-time (destruído Mar 18) |

> **Custo normalizado Mar/26** (excluindo eventos one-time MSK $27.04 e Kinesis sprint $41.83): ~$21.68 — alinhado com baseline esperado de PRD operacional ($20–35/mês).
> **MSK confirmado destruído** em 2026-03-19 — custo $27.04 foi one-time. Sem recorrência esperada.

---

## 4. DBU Databricks (PRD)

| Pipeline / Workflow | Tipo | DBU est./mês | Custo est. (USD) |
|---------------------|------|-------------|-----------------|
| `pipeline_ethereum` (DLT Streaming) | Serverless DLT | ~80 DBU | ~$5.60–11.20 |
| `pipeline_app_logs` (DLT Streaming) | Serverless DLT | ~20 DBU | ~$1.40–2.80 |
| Workflows batch (periodic + DDL) | Jobs Compute | ~20 DBU | ~$3.00 |
| **Total** | | **~120 DBU** | **~$10–17** |

> Consultar Databricks UI: **Workflows → Pipeline → Run details → DBU consumption** para valores reais. Workspace em fase de deploy em 2026-03-22.

---

## 5. Budget Alerts

| Ambiente | Threshold | Status | Configurado em |
|----------|-----------|--------|----------------|
| PRD (AWS + Databricks) | $100/mês | ⬜ pendente | — |
| DEV + HML | $30/mês | ⬜ pendente | — |

> Configurar via AWS Budgets (`aws budgets create-budget`) com notificação por SNS/email.

---

## 6. Estratégias de Otimização

### 🔴 Crítico

- [x] **MSK Kafka destruído**: cluster da arquitetura anterior destruído em 2026-03-19. Custo $27.04 foi **one-time**. `aws kafka list-clusters` confirma nenhum cluster ativo.
- [ ] **DEV Kinesis ON_DEMAND**: streams DEV custam ~$8–12/dia quando ativos. **Destruir após cada sprint de desenvolvimento** — não manter 24/7. Custo mensal potencial: ~$300/mês se não gerenciado.

### 🟡 Importante

- [ ] **PRD ECS ainda não provisionado**: executar `deploy_cloud_infra.yml` com `environment=prd` para ativar infra PRD (ECS, Databricks, Lambda PRD)
- [ ] **Kinesis ON_DEMAND → PROVISIONED**: avaliar migração para modo PROVISIONED (1 shard) após estabilização de throughput — economia ~30% em uso contínuo
- [ ] **ECS Fargate scheduled scale-down**: reduzir `desired_count=0` fora de horário de testes (23h–06h BRT) via EventBridge — economia ~40% no ECS

### 🟢 Boas Práticas

- [x] **HML Kinesis efêmero**: streams HML criados e destruídos por CI run — sem custo contínuo ✅
- [x] **Terraform-only**: toda infra gerenciada por código, sem recursos manuais ✅
- [ ] **S3 Lifecycle rules**: mover `raw/` > 90 dias para S3 Glacier Instant Retrieval — economia ~$1–2/mês
- [ ] **CloudWatch Logs retention**: TTL 30 dias para log groups não-críticos
- [ ] **Propagação de tags AWS**: garantir `project=dd-chain-explorer` em todos os recursos para rastreamento correto no Cost Explorer

---

## 7. Avaliação de Novos Recursos

> Adicionar uma sub-seção aqui antes de decidir implementar qualquer novo recurso AWS.

_(nenhuma avaliação pendente)_
