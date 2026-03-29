# 08 — Report FinOps

> **Gerado em:** 2026-03-28 | **Período:** 2026-03 (MTD) | **Região AWS:** sa-east-1
> **Gerado pelo workflow:** `/report-finops`

---

## 1. Inventário de Recursos por Ambiente

> **Status em 2026-03-28:** DEV ativo com nova arquitetura Kinesis B+C (1 PROVISIONED shard + 4 Firehose). HML idle (ECS 0 tasks). PRD ECS cluster inativo.

### DEV

| Recurso | Nome / Spec | Status | Custo Est. USD/mês |
|---------|-------------|--------|---------------------|
| Kinesis Stream (1) | `mainnet-transactions-data-dev` — PROVISIONED 1 shard | ✅ ACTIVE | ~$14.40 |
| Kinesis Firehose (4) | `firehose-mainnet-blocks-data-dev`, `firehose-mainnet-transactions-data-dev`, `firehose-mainnet-transactions-decoded-dev`, `firehose-app-logs-dev` — Direct Put | ✅ ACTIVE | ~$0.18 |
| SQS Queues (4) | `mainnet-mined-blocks-events-dev` + DLQ, `mainnet-block-txs-hash-id-dev` + DLQ | ✅ ACTIVE | ~$0.10 |
| S3 Bucket | `dm-chain-explorer-dev-ingestion` | ✅ ACTIVE | ~$0.10 |
| DynamoDB Table | `dm-chain-explorer-dev` — On-demand | ✅ ACTIVE | ~$0.10 |
| Lambda (2) | `dd-chain-explorer-dev-gold-to-dynamodb` ✅ (ativa) · `dm-chain-explorer-gold-to-dynamodb-dev` ⚠️ (duplicata legada — remover) | ✅ / ⚠️ | < $0.01 |
| ECR | `onchain-stream-txs` (account-level, shared DEV/PRD) | ✅ ACTIVE | ~$0.03 |
| ECS Cluster | `cluster-docker-on-prem` — 0 tasks ativas (idle) | ✅ IDLE | $0 |
| Databricks Free Edition | DEV workspace — DLT DEV mode, workflows batch | ✅ ACTIVE | $0 (Free) |
| **Total DEV (mensal estimado)** | | | **~$15.00** |

### HML

| Recurso | Nome / Spec | Status | Custo Est. USD/mês |
|---------|-------------|--------|---------------------|
| ECS Cluster | `cluster-docker-on-prem` (compartilhado) — 0 serviços HML ativos | ✅ IDLE | $0 |
| Kinesis Stream (1) | `mainnet-transactions-data-hml` — PROVISIONED (criado/destruído por CI) | ♻️ Efêmero | ~$0.05/run |
| Kinesis Firehose (1) | `firehose-app-logs-hml` (persistente) | ✅ ACTIVE | < $0.01 |
| SQS Queues (4) | `mainnet-mined-blocks-events-hml` + DLQ, `mainnet-block-txs-hash-id-hml` + DLQ | ✅ ACTIVE | < $0.01 |
| S3 Buckets (3) | `dm-chain-explorer-hml-*` (raw, lakehouse, databricks) — lifecycle 7/30 dias | ✅ ACTIVE | < $0.01 |
| DynamoDB Table | `dm-chain-explorer-hml` — On-demand | ✅ ACTIVE | < $0.01 |
| Databricks Free Edition | HML workspace — compartilhado com DEV | ✅ ACTIVE | $0 (Free) |
| IAM Roles | ECS, Firehose, Lambda (persistentes) | ✅ ACTIVE | $0 |
| **Total HML (mensal)** | | | **~$11.00** (1 Kinesis PROVISIONED idle) |

### PRD

| Recurso | Nome / Spec | Status | Custo Est. USD/mês |
|---------|-------------|--------|---------------------|
| VPC + NAT Gateway + Elastic IP | VPC dedicada — custo fixo | ✅ ACTIVE | ~$2.29 |
| ECS Cluster | `dm-chain-explorer-ecs` | ❌ INACTIVE (aguarda `deploy_cloud_infra prd`) | — |
| S3 `dm-chain-explorer-terraform-state` | TF backend | ✅ ACTIVE | < $0.01 |
| DynamoDB `dm-chain-explorer-terraform-lock` | TF lock | ✅ ACTIVE | < $0.01 |
| Route 53 | Hosted zone(s) | ✅ ACTIVE | ~$1.00/zona |
| ECR | `onchain-stream-txs`, `onchain-batch-txs` | ✅ ACTIVE | ~$0.03 |
| IAM Roles | ECS, Lambda, Firehose, Databricks cross-account | ✅ ACTIVE | $0 |
| Databricks (AWS workspace) | `services/prd/05_databricks` — não deployado | ❌ não criado | — |
| ECS Fargate (5 serviços 24/7) | 0.25 vCPU / 0.5 GB cada | ❌ não ativo | ~$12–18 (estimativa) |
| **Total PRD atual** | | | **~$3.30** |
| **Total PRD alvo (pós-deploy completo)** | | | **~$37–52** |

---

## 2. Custo Real — AWS Cost Explorer (2026-03 MTD, conta completa)

> **Nota:** filtro por tag `project=dd-chain-explorer` retornou $0 — recursos não possuem a tag aplicada. Custo abaixo é da **conta inteira** (inclui recursos de outros projetos). Ver Seção 6 — ação de tagging.

| Serviço AWS | Custo USD (mar/26 MTD até 28/03) | Δ vs 24/03 | Observação |
|-------------|----------------------------------:|-----------|------------|
| Amazon Kinesis | $50.91 | +$9.08 | ⚠️ ON_DEMAND 3 streams (Mar 19–23, ~$8/dia) + PROVISIONED 1 shard (Mar 24–28). Custo ON_DEMAND foi one-time. |
| Amazon MSK / Kafka | $27.04 | $0 | Cluster destruído Mar 19. Custo **one-time**, sem recorrência. |
| Tax | $13.17 | +$2.09 | Impostos proporcionais ao aumento de uso |
| Amazon ECS (Fargate) | $4.01 | +$1.02 | CI/CD HML runs + mais runs de teste ao longo do mês |
| Amazon EC2 Compute | $3.11 | +$2.30 | ⚠️ Spike — build activity intensiva pós-Mar 24. Investigar instâncias EC2 ativas. |
| Amazon Route 53 | $3.00 | +$1.00 | ⚠️ Aumento — verificar se nova hosted zone foi criada |
| Amazon Virtual Private Cloud | $2.29 | +$0.22 | NAT Gateway + VPC endpoints |
| Amazon Simple Storage Service | $1.87 | +$0.13 | Buckets de dados + TF state + logs |
| EC2 - Other | $1.55 | +$1.26 | EBS, snapshots, bandwidth |
| Amazon DynamoDB | $0.78 | +$0.29 | Tabelas dev/hml + TF lock + aumento de operações |
| AWS Cost Explorer | $0.24 | +$0.09 | API queries (este próprio workflow conta) |
| Amazon Kinesis Firehose | $0.18 | +$0.15 | 4 streams DEV ativos (Kinesis B+C migração) |
| Amazon EC2 Container Registry (ECR) | $0.03 | +$0.01 | Imagens acumuladas |
| AWS Key Management Service | $0.03 | +$0.02 | Chaves de criptografia |
| AWS Secrets Manager | $0.01 | novo | Primeiro uso no mês |
| Amazon Elastic File System | < $0.01 | — | EFS residual |
| **TOTAL** | **$108.22** | **+$17.67** | |

### Custo normalizado Mar/26 (excluindo one-times)

| Componente | Valor |
|-----------|------:|
| Total bruto | $108.22 |
| (−) MSK one-time | −$27.04 |
| (−) Kinesis ON_DEMAND sprint (estimado $8/dia × 5 dias) | −$40.00 |
| **Baseline recorrente estimado** | **~$41.18** |

> Baseline $41 alinhado com cenário DEV ativo (1 Kinesis PROVISIONED $14/mês) + infra base PRD ($3) + HML idle ($11). Aceitável para fase de desenvolvimento.

---

## 3. Tendência Mensal

| Mês | Total AWS (USD) | Top Driver | Observação |
|-----|---------------:|------------|------------|
| 2025-12 | $4.92 | VPC $3.72 | Baseline: apenas infra base (VPC + Route 53 + S3 + ECR) |
| 2026-01 | $4.92 | VPC $3.72 | Idêntico — sem ECS/Kinesis ativos |
| 2026-02 | $12.42 | ECS $5.22 | Primeiro deploy ECS + MSK inicial |
| 2026-03 | $108.22 ⚠️ | Kinesis $50.91 + MSK $27.04 | Sprint dev ativo + MSK one-time + EC2 spike |

> **Projeção Abr/26** (sem eventos one-time, DEV com 1 PROVISIONED shard): ~$30–45/mês.

---

## 4. DBU Databricks (Free Edition — DEV/HML, workspace compartilhado)

| Pipeline / Workflow | Tipo | DBU est./mês | Custo est. (USD) |
|---------------------|------|-------------|-----------------|
| `pipeline_ethereum` (DLT) | Serverless DLT DEV mode | ~40 DBU | $0 (Free Edition) |
| `pipeline_app_logs` (DLT) | Serverless DLT DEV mode | ~20 DBU | $0 (Free Edition) |
| `dm-trigger-all-dlts` (schedule 10 min DEV) | Jobs | ~10 DBU | $0 (Free Edition) |
| `dm-ddl-setup` | Jobs | ~5 DBU/run | $0 (Free Edition) |
| **Total DEV/HML** | | **~75 DBU** | **$0** |

> **PRD (workspace AWS separado — não deployado ainda):** estimativa pós-deploy ~120 DBU/mês ≈ $8–17/mês. Pipelines DLT a cada 3 min (ethereum) e 3 min offset 2 min (app_logs).

---

## 5. Budget Alerts

| Ambiente | Threshold | Status | Configurado em |
|----------|-----------|--------|----------------|
| Conta total (AWS) | $120/mês | ⬜ pendente | — |
| DEV + HML | $50/mês | ⬜ pendente | — |

> Configurar via AWS Budgets (`aws budgets create-budget`) com notificação por SNS/email.

---

## 6. Estratégias de Otimização

### 🔴 Crítico

- [x] **MSK Kafka destruído**: custo $27.04 foi one-time. `aws kafka list-clusters` confirma nenhum cluster ativo.
- [x] **Kinesis ON_DEMAND → PROVISIONED**: migração B+C implementada em Mar/26. DEV agora tem apenas 1 shard PROVISIONED (~$14/mês) + 4 Firehose Direct Put (~$0.18/mês). Economia: ~$236/mês vs. 3 streams ON_DEMAND ativos 24/7.
- [ ] **Lambda duplicada**: `dm-chain-explorer-gold-to-dynamodb-dev` é versão legada — **remover** via `aws lambda delete-function`. Apenas `dd-chain-explorer-dev-gold-to-dynamodb` é a versão ativa.
- [ ] **EC2 spike ($3.11)**: investigar instâncias EC2 ativas em sa-east-1. Pode ser instância de build não terminada. Comando: `aws ec2 describe-instances --region sa-east-1 --filters Name=instance-state-name,Values=running`.
- [ ] **Route 53 aumento ($3.00, +$1.00)**: verificar se nova hosted zone foi criada acidentalmente: `aws route53 list-hosted-zones`.

### 🟡 Importante

- [ ] **PRD ECS ainda não provisionado**: executar `deploy_cloud_infra.yml` com `environment=prd` para ativar infra PRD
- [ ] **HML Kinesis PROVISIONED idle**: `mainnet-transactions-data-hml` está ativo permanentemente (~$11/mês). Considerar destroy quando não há CI runs agendados.
- [ ] **ECS Fargate scheduled scale-down**: `desired_count=0` fora de horário de testes via EventBridge — economia ~40% no ECS

### 🟢 Boas Práticas

- [x] **HML Kinesis efêmero via CI**: streams HML recriados por CI run — reduz custo fixo ✅
- [x] **Terraform-only**: toda infra gerenciada por código ✅
- [x] **Kinesis B+C migração**: 2 streams eliminados, substituídos por Firehose Direct Put ✅
- [x] **DLT sequential DEV/HML**: `dm-trigger-all-dlts` evita quota violation no workspace compartilhado ✅
- [ ] **Propagação de tags AWS**: aplicar `project=dd-chain-explorer` + `environment=dev/hml/prd` em todos os recursos para rastreamento no Cost Explorer
- [ ] **S3 Lifecycle rules**: mover `raw/` > 90 dias para S3 Glacier Instant Retrieval — economia ~$1–2/mês
- [ ] **CloudWatch Logs retention**: TTL 30 dias para log groups não-críticos

---

## 7. Avaliação de Novos Recursos

> Adicionar uma sub-seção aqui antes de decidir implementar qualquer novo recurso AWS.

_(nenhuma avaliação pendente)_
