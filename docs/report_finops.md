# 08 — Report FinOps

> **Gerado em:** 2026-03-21 | **Período:** 2026-03 | **Região AWS:** sa-east-1
> **Gerado pelo workflow:** `/report-finops`

---

## 1. Inventário de Recursos por Ambiente

### DEV

| Recurso | Spec | Custo Estimado (USD/mês) | Custo Real |
|---------|------|--------------------------|------------|
| Kinesis Data Streams (3) | ON_DEMAND — `mainnet-blocks-data`, `mainnet-transactions-data`, `mainnet-transactions-decoded` | ~$3–6 | a medir |
| SQS Queues (4) | Standard — `mainnet-block-txs-hash-id-dev`, `mainnet-mined-blocks-events-dev` + DLQs | ~$0.50 | a medir |
| S3 Bucket | `dm-chain-explorer-dev-ingestion` — ~5 GB | ~$0.50 | a medir |
| DynamoDB Table | `dm-chain-explorer` — On-demand | ~$1 | a medir |
| Lambda `gold_to_dynamodb` | Python 3.12, 128 MB, ~1K invocações/mês | ~$0.10 | a medir |
| CloudWatch Logs | Kinesis + Lambda + app logs | ~$1–2 | a medir |
| Firehose (3) | ~500 MB/mês para S3 | ~$1 | a medir |
| **Total DEV** | | **~$7–11** | |

### HML

| Recurso | Spec | Custo Estimado (USD/mês) | Custo Real |
|---------|------|--------------------------|------------|
| S3 Bucket | `dm-chain-explorer-hml-ingestion` — ~1 GB | ~$0.20 | a medir |
| IAM Roles | ECS task execution, task role, Firehose role | $0 | $0 |
| CloudWatch Log Group | `/ecs/dm-chain-explorer-hml` + Firehose | ~$0.50 | a medir |
| Firehose (ephemeral) | Criado/destruído por CI/CD run | ~$0.20 | a medir |
| **Total HML** | | **~$0.90–1** | |

> HML usa recursos efêmeros (ECS, Kinesis, SQS, DynamoDB) criados e destruídos por CI/CD run. Custo marginal por execução < $0.10.

### PRD

| Recurso | Spec | Custo Estimado (USD/mês) | Custo Real |
|---------|------|--------------------------|------------|
| VPC + Subnets + SGs | 2 subnets públicas, sem NAT Gateway | ~$0 | $0 |
| IAM Roles | ECS execution, task, Firehose, Lambda, Databricks cross-account | $0 | $0 |
| Kinesis Data Streams (5) | ON_DEMAND — blocks, txs, decoded, receipts, logs | ~$8–12 | a medir |
| SQS Queues (6) | Standard + DLQs | ~$1 | a medir |
| Kinesis Firehose (5) | S3 delivery ~1 GB/mês total | ~$2–3 | a medir |
| S3 `dm-chain-explorer-raw-data` | Raw Kinesis data — ~20 GB/mês | ~$3 | a medir |
| S3 `dm-chain-explorer-lakehouse` | Delta tables (Bronze/Silver/Gold) — ~30 GB | ~$4 | a medir |
| S3 `dm-chain-explorer-databricks` | Checkpoints, staging — ~5 GB | ~$0.50 | a medir |
| DynamoDB `dm-chain-explorer` | On-demand, ~1M WCU/mês | ~$3–5 | a medir |
| ECS Cluster + 5 Services | Fargate 0.25 vCPU / 0.5 GB cada, ~720h/mês | ~$12–18 | a medir |
| ECR (2 repos) | `onchain-stream-txs`, `onchain-batch-txs` | ~$0.50 | a medir |
| Lambda `contracts_ingestion` | Python 3.12, 256 MB, ~720 invocações/mês | ~$0.50 | a medir |
| Lambda `gold_to_dynamodb` | Python 3.12, 128 MB, ~100 invocações/mês | ~$0.10 | a medir |
| CloudWatch Logs | ECS + Lambda + Firehose | ~$3–5 | a medir |
| EventBridge Scheduler | 1 regra (contracts_ingestion hourly) | ~$0.10 | a medir |
| **Total PRD (AWS)** | | **~$37–52** | |
| **Databricks DLT (PRD)** | Serverless Streaming ~100 DBU/mês + Jobs ~20 DBU | ~$10–17 | a medir |
| **Total PRD (AWS + Databricks)** | | **~$47–69** | |

---

## 2. Custo Real — AWS Cost Explorer

> Execute o workflow `/report-finops` Step 2 para preencher esta seção com dados reais.

| Ambiente | Serviço AWS | Custo USD (mês atual) |
|----------|-------------|----------------------|
| _(executar `/report-finops`)_ | | |

```bash
# Comando rápido para consulta manual:
python3 - <<'EOF'
import boto3
from datetime import date
ce = boto3.client("ce", region_name="us-east-1")
today = date.today()
resp = ce.get_cost_and_usage(
    TimePeriod={"Start": today.replace(day=1).isoformat(), "End": today.isoformat()},
    Granularity="MONTHLY",
    Filter={"Tags": {"Key": "project", "Values": ["dd-chain-explorer"]}},
    GroupBy=[{"Type": "TAG", "Key": "environment"}, {"Type": "DIMENSION", "Key": "SERVICE"}],
    Metrics=["UnblendedCost"],
)
for g in resp["ResultsByTime"][0]["Groups"]:
    env, svc = g["Keys"]
    cost = float(g["Metrics"]["UnblendedCost"]["Amount"])
    if cost > 0.0001:
        print(f"{env:<20} {svc:<45} ${cost:.4f}")
EOF
```

---

## 3. Tendência Mensal

> Preencher após execução do workflow `/report-finops` Step 2.

| Mês | Total AWS (USD) | Total Databricks (USD) | Total |
|-----|----------------|------------------------|-------|
| 2026-01 | a medir | a medir | — |
| 2026-02 | a medir | a medir | — |
| 2026-03 | a medir | a medir | — |

---

## 4. DBU Databricks (PRD)

| Pipeline / Workflow | Tipo | DBU est./mês | Custo est. (USD) |
|---------------------|------|-------------|-----------------|
| `pipeline_ethereum` (DLT Streaming) | Serverless DLT | ~80 DBU | ~$5.60–11.20 |
| `pipeline_app_logs` (DLT Streaming) | Serverless DLT | ~20 DBU | ~$1.40–2.80 |
| Workflows batch (periodic + DDL) | Jobs Compute | ~20 DBU | ~$3.00 |
| **Total** | | **~120 DBU** | **~$10–17** |

> Consultar Databricks UI: **Workflows → Pipeline → Run details → DBU consumption** para valores reais.

---

## 5. Budget Alerts

| Ambiente | Threshold | Status | Configurado em |
|----------|-----------|--------|----------------|
| PRD (AWS + Databricks) | $100/mês | ⬜ pendente | — |
| DEV + HML | $30/mês | ⬜ pendente | — |

> Configurar via AWS Budgets (`aws budgets create-budget`) com notificação por SNS/email.

---

## 6. Estratégias de Otimização

- [ ] **ECS Fargate**: reduzir `desired_count` para 0 em horários sem tráfego (23h–06h BRT) via EventBridge schedule — economia estimada ~40%
- [ ] **Kinesis ON_DEMAND → PROVISIONED**: migrar se throughput for estável e previsível (< 1 shard) — economia ~30%
- [ ] **DLT Serverless**: verificar se `autoscale` reduz DBU vs workers fixos
- [ ] **S3 Lifecycle**: mover `raw/` com > 90 dias para S3 Glacier Instant Retrieval — economia ~$1–2/mês
- [ ] **CloudWatch Logs retention**: definir TTL de 30 dias para log groups não-críticos

---

## 7. Avaliação de Novos Recursos

> Adicionar uma sub-seção aqui antes de decidir implementar qualquer novo recurso AWS.

_(nenhuma avaliação pendente)_
