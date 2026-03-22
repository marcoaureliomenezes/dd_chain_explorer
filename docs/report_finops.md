# 08 — Report FinOps

> **Gerado em:** 2026-03-22 | **Período:** 2026-03 | **Região AWS:** sa-east-1
> **Gerado pelo workflow:** `/report-finops`

---

## 1. Inventário de Recursos por Ambiente

> **Status em 2026-03-22:** infra PRD em fase de redeploy (refatoração módulo Databricks). Recursos abaixo refletem o estado alvo pós-deploy completo.

### DEV

| Recurso | Spec | Custo Estimado (USD/mês) | Status atual |
|---------|------|--------------------------|--------------|
| Kinesis Data Streams (3) | ON_DEMAND — `mainnet-blocks-data`, `mainnet-transactions-data`, `mainnet-transactions-decoded` | ~$3–6 | ⬜ destruído (redeploy em curso) |
| SQS Queues (4) | Standard — filas de blocos/txs + DLQs | ~$0.50 | ⬜ destruído |
| S3 Bucket | `dm-chain-explorer-dev-ingestion` — ~5 GB | ~$0.50 | ⬜ destruído |
| DynamoDB Table | `dm-chain-explorer` — On-demand | ~$1 | ⬜ destruído |
| Lambda `gold_to_dynamodb` | Python 3.12, 128 MB, ~1K invocações/mês | ~$0.10 | ⬜ destruído |
| CloudWatch Logs | Kinesis + Lambda + app logs | ~$1–2 | ⬜ destruído |
| Firehose (3) | ~500 MB/mês para S3 | ~$1 | ⬜ destruído |
| **Total DEV** | | **~$7–11** | |

### PRD

| Recurso | Spec | Custo Estimado (USD/mês) | Status atual |
|---------|------|--------------------------|--------------|
| VPC + Subnets + SGs | 2 subnets privadas, sem NAT Gateway | ~$0 | ✅ deployado |
| IAM Roles | ECS execution, task, Firehose, Lambda, Databricks cross-account | $0 | ✅ deployado |
| S3 `dm-chain-explorer-terraform-state` | Remote state + DynamoDB lock | ~$0.10 | ✅ sempre ativo |
| S3 `dm-chain-explorer-raw` | Raw Kinesis data — ~20 GB/mês | ~$3 | ✅ deployado |
| S3 `dm-chain-explorer-lakehouse` | Delta/Iceberg tables (Bronze/Silver/Gold) — ~30 GB | ~$4 | ✅ deployado |
| S3 `dm-chain-explorer-databricks` | Checkpoints, staging, Unity Catalog — ~5 GB | ~$0.50 | ✅ deployado |
| ECR (2 repos) | `onchain-stream-txs`, `onchain-batch-txs` | ~$0.50 | ✅ deployado |
| Kinesis Data Streams (5) | ON_DEMAND — blocks, txs, decoded, receipts, logs | ~$8–12 | ✅ deployado |
| SQS Queues (6) | Standard + DLQs | ~$1 | ✅ deployado |
| Kinesis Firehose (5) | S3 delivery ~1 GB/mês total | ~$2–3 | ✅ deployado |
| DynamoDB `dm-chain-explorer` | On-demand, ~1M WCU/mês | ~$3–5 | ✅ deployado |
| ECS Cluster + 5 Services | Fargate 0.25 vCPU / 0.5 GB cada, ~720h/mês | ~$12–18 | ✅ deployado |
| Lambda `contracts_ingestion` | Python 3.12, 256 MB, ~720 invocações/mês | ~$0.50 | ✅ deployado |
| Lambda `gold_to_dynamodb` | Python 3.12, 128 MB, ~100 invocações/mês | ~$0.10 | ✅ deployado |
| CloudWatch Logs | ECS + Lambda + Firehose | ~$3–5 | ✅ deployado |
| EventBridge Scheduler | 1 regra (`contracts_ingestion` hourly) | ~$0.10 | ✅ deployado |
| Databricks Workspace | MWS workspace `dm-chain-explorer-prd` (sa-east-1) | — | 🔄 em deploy |
| Databricks Metastore | Unity Catalog `dm-chain-explorer-metastore` | — | 🔄 em deploy |
| **Total PRD (AWS)** | | **~$37–52** | |
| **Databricks DLT (PRD)** | Serverless Streaming ~100 DBU/mês + Jobs ~20 DBU | ~$10–17 | 🔄 em deploy |
| **Total PRD (AWS + Databricks)** | | **~$47–69** | |

---

## 2. Custo Real — AWS Cost Explorer (2026-03-01 → 2026-03-22)

> Dados obtidos via `boto3` Cost Explorer SDK em 2026-03-22. **Nota:** tags `project=dd-chain-explorer` ainda não propagadas para todos os recursos — custo real total mostrado na seção "sem filtro de tag".

### Por tag `project=dd-chain-explorer`

| Serviço AWS | Custo USD (mar/26) |
|-------------|-------------------|
| _(sem custo rastreado por tag no período — tags em propagação)_ | $0.0000 |

### Total real (todos os recursos AWS, sem filtro de tag)

| Serviço AWS | 2026-03 (até dia 22) |
|-------------|----------------------|
| Amazon Managed Streaming for Apache Kafka | $27.0425 |
| Amazon Kinesis | $24.3193 |
| Tax | $8.3100 |
| Amazon Elastic Container Service | $2.4118 |
| Amazon Virtual Private Cloud | $2.0405 |
| Amazon Simple Storage Service | $1.7067 |
| Amazon Route 53 | $1.5023 |
| Amazon DynamoDB | $0.4873 |
| Amazon Elastic Compute Cloud - Compute | $0.2347 |
| AWS Cost Explorer | $0.0900 |
| EC2 - Other | $0.0800 |
| Amazon Kinesis Firehose | $0.0252 |
| Amazon EC2 Container Registry (ECR) | $0.0174 |
| AWS Key Management Service | $0.0004 |
| **TOTAL** | **$68.27** |

> ⚠️ **MSK (Kafka $27.04) e Kinesis ($24.32) dominam o custo de março.** MSK foi removido da arquitetura — verificar se ainda há cluster ativo e destruir se necessário.

---

## 3. Tendência Mensal

| Mês | Total AWS (USD) | Observação |
|-----|----------------|------------|
| 2025-12 | $4.92 | Apenas VPC + Route53 + S3 + ECR (infra base) |
| 2026-01 | $4.92 | Idem — sem ECS/Kinesis ativos |
| 2026-02 | $12.42 | ECS ($5.22) + MSK ($0.77) + VPC + S3 — primeiro deploy |
| 2026-03 | $68.27 ⚠️ | MSK ($27.04) + Kinesis ($24.32) — pico por recursos não destruídos |

> **Ação urgente:** MSK (Kafka) de $27/mês não está na arquitetura alvo. Verificar e destruir cluster MSK remanescente.

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

- [ ] **🔴 URGENTE — MSK Kafka**: cluster `$27/mês` ativo mas fora da arquitetura alvo — destruir imediatamente (`aws kafka list-clusters`)
- [ ] **Kinesis ON_DEMAND → PROVISIONED**: migrar se throughput estabilizar abaixo de 1 shard — economia ~30%
- [ ] **ECS Fargate**: reduzir `desired_count` para 0 fora de horário de testes (23h–06h BRT) via EventBridge — economia ~40%
- [ ] **DLT Serverless**: verificar se `autoscale` reduz DBU vs workers fixos
- [ ] **S3 Lifecycle**: mover `raw/` > 90 dias para S3 Glacier Instant Retrieval — economia ~$1–2/mês
- [ ] **CloudWatch Logs retention**: TTL 30 dias para log groups não-críticos
- [ ] **Propagação de tags AWS**: garantir `project=dd-chain-explorer` em todos os recursos para rastreamento correto no Cost Explorer

---

## 7. Avaliação de Novos Recursos

> Adicionar uma sub-seção aqui antes de decidir implementar qualquer novo recurso AWS.

_(nenhuma avaliação pendente)_
