# 06 — FinOps & Análise de Custos

## Visão Geral

Este documento detalha os custos operacionais do **DD Chain Explorer** em todos os ambientes (DEV, HML, PROD), cobrindo tanto a infraestrutura AWS quanto o consumo Databricks (DBUs). O objetivo é fornecer visibilidade total de gastos, identificar oportunidades de otimização e manter um roadmap acionável de redução de custos.

> **Modelo de custos dual**: O projeto incorre em custos em **duas camadas** independentes:
> 1. **AWS** — VPC, ECS Fargate, Kinesis, SQS, Firehose, CloudWatch, S3, DynamoDB, Lambda, ECR, Route 53
> 2. **Databricks** — DBUs (Databricks Units) cobrados por segundo de uso de compute

---

## 1. Inventário de Recursos por Ambiente

### 1.1 DEV — Desenvolvimento Local

| Recurso | Tipo | Custo Mensal | Observação |
|---------|------|-------------|------------|
| Databricks Free Edition | Workspace gratuito | $0 | Compute serverless limitado, sem SLA |
| S3 `dm-chain-explorer-dev-ingestion` | Bucket | ~$0.02 | Dados NDJSON via Firehose |
| Kinesis Data Streams (3) | On-demand | ~$0.10 | Streams de dados |
| SQS (2 filas + 2 DLQs) | Standard | ~$0 | Coordenação inter-job |
| CloudWatch Logs | Log group | ~$0.01 | Logs de aplicação |
| Firehose (4 delivery streams) | On-demand | ~$0.05 | Entrega NDJSON no S3 |
| DynamoDB `dm-chain-explorer` | On-demand | ~$0.05 | Single-table design, TTL ativo |
| Lambda `gold-to-dynamodb` | 128 MB, Python 3.12 | ~$0 | Invocações mínimas |
| Lambda `contracts-ingestion` | 256 MB, Python 3.12 | ~$0 | EventBridge hourly, invocações mínimas |
| Docker local | 5 jobs streaming | $0 | Roda na máquina do desenvolvedor |

**Total DEV: ~$0.23/mês** (custo AWS negligível)

### 1.2 HML — Homologação

| Recurso | Tipo | Custo Mensal | Observação |
|---------|------|-------------|------------|
| Databricks Free Edition | Mesmo workspace do DEV (catálogo `hml`) | $0 | — |
| S3 `dm-chain-explorer-hml-ingestion` | Bucket, lifecycle 7d | ~$0.01 | Dados expiram automaticamente |
| DynamoDB `dm-chain-explorer-hml` | On-demand | ~$0.01 | Uso apenas durante CI/CD |
| IAM roles | `dm-hml-ecs-task-*` | $0 | — |
| ECS (efêmero) | Criado/destruído por run CI/CD | $0~$0.50/run | Fargate Spot, ~30 min por run |

**Total HML: ~$0.02/mês** + ~$0.50/run de CI/CD

### 1.3 PRD — Produção

| Recurso | Terraform Module | Tipo / Spec | Custo/Mês (estimado 24/7) | Custo/Mês (uso intermitente) |
|---------|------------------|-------------|---------------------------|------------------------------|
| **VPC** | `1_vpc` | 1 public + 2 private subnets, IGW, S3 VPC Endpoint | ~$3.60 (EIPs) | $0 (sem EIP ociosa¹) |
| **Kinesis Data Streams** | `3_kinesis_sqs` | 3 streams on-demand | ~$3-8/mês | ~$1-3 (1 semana) |
| **SQS** | `3_kinesis_sqs` | 2 filas + 2 DLQs | ~$0.01 | ~$0 |
| **Firehose** | `3_kinesis_sqs` | 4 delivery streams → S3 | ~$2-5/mês | ~$0.50 |
| **CloudWatch Logs** | `3_kinesis_sqs` | 1 log group + subscription filter | ~$1-3/mês | ~$0.30 |
| **ECS Fargate** | `6_ecs` | 5 services, 12 tasks (0.25 vCPU, 512 MB cada) | ~$36/mês | $5.40 (uso intermitente) |
| **Databricks Workspace** | `7_databricks` | MWS workspace, sa-east-1 | ver seção 3 | ver seção 3 |
| **Databricks Cluster** | `7_databricks` | 1 driver + 1 worker, auto-term 60 min | ver seção 3 | ver seção 3 |
| **S3 (3 buckets)** | `4_s3` | raw + lakehouse + databricks | ~$1.50/mês | ~$0.40 |
| **DynamoDB** | `9_dynamodb` | On-demand, PITR, encryption | ~$0.50/mês | ~$0.15 |
| **Lambda** | `10_lambda` | gold_to_dynamodb, 128 MB | ~$0 | ~$0 |
| **ECR** | `6_ecs` | 2 repos (stream + batch) | ~$0.03 | ~$0.03 |
| **Route 53** | externo | Hosted zone | ~$0.50 | ~$0.50 |

> ¹ EIP ociosa `ChainExplorer-nat-eip` foi **removida** em 17/Mar/2026 (economia: $3.60/mês).
> ² MSK removido em Mar/2026, substituído por Kinesis/SQS/CloudWatch/Firehose (eliminados: MSK, KMS, ElastiCache, Schema Registry).

**Total PRD estimado 24/7: ~$70/mês** (AWS) + Databricks DBUs
**Total PRD real (uso intermitente): ~$8–12/mês**

---

## 2. Análise de Custos AWS — Dados Reais

Dados extraídos via AWS Cost Explorer (Out/2025 — Mar/2026).

### 2.1 Custos Mensais por Serviço

| Mês | VPC | ECS | MSK | S3 | Route 53 | ElastiCache | DynamoDB | ECR | KMS | Tax | **Total** |
|-----|-----|-----|-----|----|---------:|-------------|----------|-----|-----|-----|-----------|
| Out/25 | $3.72 | — | — | $0.08 | $0.50 | — | — | $0.03 | — | $0.59 | **$4.92** |
| Nov/25 | $3.60 | — | — | $0.08 | $0.50 | — | — | $0.03 | — | $0.58 | **$4.79** |
| Dez/25 | $3.72 | — | — | $0.08 | $0.50 | — | — | $0.03 | — | $0.59 | **$4.92** |
| Jan/26 | $3.72 | — | — | $0.08 | $0.50 | — | — | $0.03 | — | $0.59 | **$4.92** |
| Fev/26 | $3.68 | $5.22 | $0.77 | $0.43 | $0.50 | $0.18 | — | $0.03 | $0.01 | $1.51 | **$12.42** |
| Mar/26² | $1.94 | $1.56 | — | $1.40 | $0.50 | — | $0.15 | $0.01 | — | $0.75 | **$6.32** |

> ² Dados parciais (01–17 Mar).

### 2.2 Breakdown — Maiores Custos

#### VPC ($20.38 total, 53% dos custos)
- **$3.36/mês**: `SAE1-PublicIPv4:IdleAddress` — EIP não associada (**resolvido**: EIP removida)
- **$0.32/mês**: `SAE1-PublicIPv4:InUseAddress` — IP público em uso pelo ECS Fargate

**Após remoção da EIP ociosa**: custo VPC reduz para ~$0.32/mês (apenas IPs públicos ECS em uso).

#### ECS Fargate ($6.79 total, 18%)
- `SAE1-ECS-Anywhere-Instance-hours`: $4.26
- `SAE1-Fargate-vCPU-Hours:perCPU`: $2.06
- `SAE1-Fargate-GB-Hours`: $0.45
- Uso intermitente: 33 dias ativos em ~45 dias monitorados

#### MSK Kafka ($0.77 total, 2%)
- Ativo apenas 1 dia (22/Fev/2026)
- `SAE1-Kafka.t3.small`: $0.71 (instâncias broker)
- `SAE1-Kafka.Storage.GP2`: $0.05 (EBS storage)
- **Custo projetado 24/7**: ~$60/mês (2× kafka.t3.small @ ~$0.042/h + EBS)

### 2.3 Distribuição de Custos (6 meses acumulado)

```
VPC (EIP ociosa)     ██████████████████████████  $20.38  (53%)
ECS Fargate          ███████                     $6.79   (18%)
Tax                  █████                       $4.61   (12%)
Route 53             ███                         $3.02   (8%)
S3                   ██                          $2.16   (6%)
MSK                  █                           $0.77   (2%)
ElastiCache          ░                           $0.18   (<1%)
DynamoDB             ░                           $0.15   (<1%)
ECR                  ░                           $0.14   (<1%)
                                          Total: $38.20
```

---

## 3. Análise de Custos Databricks

O Databricks opera com um **modelo de cobrança dual**:

1. **Databricks DBUs** — cobrados diretamente pela Databricks na fatura do marketplace AWS
2. **Infraestrutura AWS** — EC2 (clusters), S3 (storage), networking (VPC, NAT) na fatura AWS

### 3.1 DEV / HML — Free Edition

| Componente | Custo |
|------------|-------|
| Workspace | $0 (Free Edition, sem SLA) |
| Compute | Serverless limitado (até 15 DBU/mês gratuitos) |
| Storage | S3 na conta AWS do usuário (custo AWS normal) |
| Networking | Nenhum custo extra (workspace gerenciado pela Databricks) |

> O Free Edition não requer VPC, NAT Gateway ou EC2 na conta do usuário.

### 3.2 PRD — Workspace AWS (MWS)

O workspace PRD é criado via `databricks_mws_workspaces` na VPC do projeto.

#### Configuração Atual
- **Região**: sa-east-1
- **VPC**: Customer-managed (`is_no_public_ip_enabled = true`)
- **S3 VPC Endpoint**: Gateway endpoint (sem NAT Gateway necessário para S3)
- **Cluster interativo**: 1 driver + 1 worker, auto-terminate 60 min
- **Unity Catalog**: Metastore próprio (`dm-chain-explorer-metastore`)

#### Custos Databricks DBU por Tipo de Compute

| Tipo de Compute | Uso no Projeto | DBU Rate (AWS Premium) | Onde é cobrado |
|-----------------|----------------|------------------------|----------------|
| **Jobs Compute (Classic)** | DLT pipelines batch | $0.15/DBU | Fatura Databricks (AWS Marketplace) |
| **DLT Core** | Pipelines streaming/batch | $0.20/DBU | Fatura Databricks |
| **DLT Pro** | Se usar CDC | $0.25/DBU | Fatura Databricks |
| **All-Purpose Compute** | Cluster interativo, notebooks | $0.40/DBU | Fatura Databricks |
| **SQL Classic** | SQL Warehouse (dashboards) | $0.22/DBU | Fatura Databricks |
| **SQL Serverless** | SQL Warehouse serverless | $0.70/DBU (inclui EC2) | Fatura Databricks |

#### Custos de Infraestrutura AWS para Databricks

| Componente AWS | Quando cobra | Custo Estimado |
|----------------|--------------|----------------|
| **EC2 (cluster nodes)** | Enquanto cluster estiver ligado | Depende do instance type (ex: m5d.large ~$0.124/h em sa-east-1) |
| **S3 (DBFS root + Unity Catalog)** | Sempre (storage) | ~$0.50/mês (volume atual baixo) |
| **S3 (checkpoints DLT)** | Sempre | Incluso acima |
| **VPC Endpoint S3 (Gateway)** | Sempre | $0 (gateway endpoints são gratuitos) |
| **NAT Gateway** | **NÃO EXISTE** no projeto¹ | $0 |
| **Data transfer intra-AZ** | Durante processamento | Negligível |

> ¹ O workspace usa `is_no_public_ip_enabled = true` com S3 Gateway Endpoint. O control plane da Databricks se comunica via SCC (Secure Cluster Connectivity) usando túnel reverso, sem necessidade de NAT Gateway. Isso **elimina** o custo de ~$32/mês que um NAT Gateway geraria.

#### Custo Databricks com Workspace Idle (parado)

| Estado | DBU Cost | EC2 Cost | S3 Cost | Total |
|--------|----------|----------|---------|-------|
| **Idle** (clusters parados, sem jobs) | $0 | $0 | ~$0.50/mês | **~$0.50/mês** |
| **DLT pipeline rodando** (1 worker) | ~2 DBU/h × $0.20 = $0.40/h | ~$0.124/h | — | **~$0.52/h** |
| **Cluster interativo** (1 worker) | ~3 DBU/h × $0.40 = $1.20/h | ~$0.248/h | — | **~$1.45/h** |
| **SQL Warehouse (Classic)** | ~2 DBU/h × $0.22 = $0.44/h | ~$0.124/h | — | **~$0.56/h** |

#### Estimativa Databricks PRD 24/7

| Cenário | Custo/Mês |
|---------|-----------|
| DLT continuous (24/7, 1 worker) | ~$375/mês (DBU: $288 + EC2: $89) |
| DLT scheduled (4h/dia) | ~$62/mês |
| SQL Warehouse (8h/dia, 20 dias) | ~$90/mês |
| Cluster interativo (2h/dia, 20 dias) | ~$58/mês |

### 3.3 Onde Verificar Custos Databricks

1. **Databricks Account Console** → Billing → Usage
   - Mostra consumo de DBUs por workspace, cluster e job
   - URL: `https://accounts.cloud.databricks.com`

2. **System Tables** (se Enterprise):
   ```sql
   SELECT sku_name, usage_date, usage_quantity, usage_unit
   FROM system.billing.usage
   WHERE workspace_id = '<workspace_id>'
   ORDER BY usage_date DESC;
   ```

3. **AWS Cost Explorer** → filtrar por tag `cost-center: dd-chain-explorer`
   - Mostra EC2, S3, data transfer gerados pelo Databricks
   - Instâncias EC2 dos clusters têm as custom_tags definidas no Terraform

4. **AWS Marketplace** → Manage subscriptions → Databricks
   - Fatura consolidada de DBUs

---

## 4. Estratégia de Tagging

### 4.1 Padrão Adotado

Todas as tags seguem o formato **kebab-case** para consistência:

| Tag | Valor | Propósito |
|-----|-------|-----------|
| `owner` | `marco-menezes` | Responsável pelo recurso |
| `managed-by` | `terraform` | Ferramenta de provisionamento |
| `cost-center` | `dd-chain-explorer` | Centro de custo para alocação |
| `environment` | `dev` / `hml` / `prd` / `shared` | Ambiente |
| `project` | `dd-chain-explorer` | Nome do projeto |
| `deploy-id` | `YYYYMMDDhhmmss` (auto) | Identifica cada deploy (destroy/recreate) |

### 4.2 Tag `deploy-id`

A tag `deploy-id` é gerada automaticamente via `formatdate("YYYYMMDDhhmmss", timestamp())` no Terraform. Isso permite:

- **Distinguir** recursos de diferentes ciclos de destroy/recreate
- **Correlacionar** custos no Cost Explorer com deploys específicos
- **Rastrear** quando o recurso foi criado sem precisar de incremento manual

> **Nota**: `timestamp()` gera um valor novo a cada `terraform plan/apply`. Para evitar diffs desnecessários, considere usar `lifecycle { ignore_changes = [tags["deploy-id"]] }` nos recursos que não são recriados frequentemente, ou mover o deploy-id para uma variável passada manualmente.

### 4.3 Correções Realizadas

| Módulo | Antes | Depois |
|--------|-------|--------|
| `8_elasticache/locals.tf` | `CostCenter`, `Project`, `ManagedBy` (PascalCase) | `cost-center`, `project`, `managed-by` (kebab-case) |
| `9_dynamodb/locals.tf` | `CostCenter`, `Project`, `ManagedBy` (PascalCase) | `cost-center`, `project`, `managed-by` (kebab-case) |
| `10_lambda/locals.tf` | `var.project` (dinâmico) | `"dd-chain-explorer"` (fixo, consistente) |
| Todos os módulos | Sem `deploy-id` | `deploy-id` adicionado |

### 4.4 Ativação de Tags no AWS Cost Explorer

Para que as tags apareçam no Cost Explorer, é necessário **ativá-las manualmente**:

1. Acessar **AWS Billing Console** → **Cost Allocation Tags**
   - URL: `https://console.aws.amazon.com/billing/home#/tags`
2. Na aba **User-defined cost allocation tags**, localizar:
   - `cost-center`
   - `environment`
   - `project`
   - `deploy-id`
3. Selecionar e clicar **Activate**
4. Aguardar **24 horas** para os dados aparecerem no Cost Explorer

> **Importante**: Tags ativadas só geram dados de custo a partir da data de ativação. Dados históricos não são retroativos.

---

## 5. Custo Projetado — PRD 24/7

Estimativa de custo mensal se todos os recursos PROD estivessem ligados 24/7:

| Componente | Antes | **Após Otimizações** | Mudança |
|------------|-------|----------------------|----------|
| Databricks DLT | $288 (continuous) | **~$62** (scheduled 5min) | ✅ Implementado |
| EC2 para Databricks clusters | $89 (On-Demand) | **~$18-35** (SPOT_WITH_FALLBACK) | ✅ Implementado |
| Kinesis/SQS/Firehose/CW | $60 (antigo MSK) | **~$6-16** | ✅ Implementado (migração completa) |
| ECS Fargate (12 tasks) | $45 | $36 | ✅ Schema Registry removido |
| SQL Warehouse (8h/dia) | $90 | **~$0-30** (Serverless, paga por query) | Pendente config |
| Databricks cluster interativo | $58 | $58 | — |
| ElastiCache Redis | $12 | **$0** (removido) | ✅ Implementado |
| Schema Registry ECS | $3 | **$0** (removido) | ✅ Implementado |
| S3 (todos os buckets) | $2 | $2 + lifecycle IA 90d | ✅ Implementado |
| Route 53 + ECR + DynamoDB | $2 | $2 | — |
| KMS | $1 | **$0** (removido) | ✅ Implementado |
| Impostos (~16%) | $103 | **~$46** | — |
| **Total** | **~$749/mês** | **~$325/mês** | **-57%** |

---

## 6. Estratégias de Otimização

### 6.1 Mensageria AWS — ✅ Kinesis/SQS/Firehose Implementado (Mar/2026)

**Antes**: MSK Serverless (Kafka) + Schema Registry ECS + Avro = ~$15-40/mês
**Depois**: Kinesis Data Streams + SQS + Firehose + CloudWatch Logs = ~$6-16/mês

| Serviço | Custo 24/7 | Custo intermitente |
|---------|-----------|-------------------|
| Kinesis Data Streams (3, on-demand) | ~$3-8/mês | ~$1-3 |
| SQS (2 filas + 2 DLQs) | ~$0.01 | ~$0 |
| Firehose (4 delivery streams) | ~$2-5/mês | ~$0.50 |
| CloudWatch Logs | ~$1-3/mês | ~$0.30 |

**Benefícios da migração**:
- Eliminação do MSK Serverless (~$15-40/mês)
- Eliminação do Schema Registry ECS task
- Eliminação do KMS (~$1/mês)
- Eliminação do ElastiCache (~$12/mês)
- Sem custo mínimo — Kinesis on-demand cobra por throughput real

### 6.2 ECS Fargate — Otimização de Compute

**Custo atual**: ~$45/mês (24/7, 15 tasks)

| Estratégia | Economia | Complexidade |
|------------|----------|--------------|
| **Fargate Spot** (já configurado como default!) | 50-70% | ✅ Já implementado |
| **Right-sizing**: reduzir de 512 MB → 256 MB se possível | ~20% | Baixa |
| **Escalar para 0 quando ocioso** (`prod_standby.sh`) | 100% quando parado | ✅ Já implementado |
| **ECS com EC2 Capacity Provider** (Spot instances) | 60-80% vs Fargate on-demand | Média |
| **Reduzir réplicas do txs_crawler** (8 → 4) | ~25% do ECS total | Baixa (testar throughput) |

**Recomendação**: O padrão `FARGATE_SPOT` já está configurado como default capacity provider. Validar que os services estão efetivamente usando Spot. Considerar reduzir `mined_txs_crawler` de 8 para 4 réplicas e monitorar o throughput.

### 6.3 Databricks — Otimização de DBUs

| Estratégia | Economia | Complexidade |
|------------|----------|--------------|
| **Auto-terminate** (60 min) | Evita idle billing | ✅ Já implementado |
| **DLT scheduled 5min** (cron nativo) | ~$313/mês ($375→$62) | ✅ **Implementado 17/Mar/2026** |
| **SPOT_WITH_FALLBACK** no cluster | 60-90% em EC2 | ✅ **Implementado 17/Mar/2026** |
| **DLT Serverless** (`serverless: true`) | Inclui Photon, no EC2 | ✅ Já estava configurado |
| **Serverless SQL Warehouse** | $0 quando sem queries | Pendente — configurar após deploy PROD |
| **Cluster policies** | Limitar instance types e workers | Baixa prioridade |

**Status pós-implementação 17/Mar/2026**:
- DLT: `serverless: true` + `continuous: false` + schedule `0 0/5 * * * ?` (pausado, ativar após smoke test)
- Cluster: `SPOT_WITH_FALLBACK` — tenta Spot, fallback para On-Demand automaticamente
- Pendente: SQL Warehouse serverless (requer workspace PROD ativo para obter `warehouse_id`)

### 6.4 Airflow — Alternativas Serverless

**Situação atual**: Airflow roda localmente via Docker Compose (PostgreSQL + Scheduler + Webserver). Para PROD, seria necessário hospedar em EC2 ou ECS.

| Alternativa | Custo Estimado | Vantagens | Desvantagens |
|-------------|----------------|-----------|--------------|
| **AWS Step Functions** | ~$0.025/1000 transições | Serverless, integra com ECS/Lambda | Sem UI rica, curva de aprendizado |
| **MWAA (Managed Airflow)** | ~$50/mês (mínimo) | Familiar, managed | Caro para uso leve |
| **EventBridge Scheduler + Lambda** | ~$0 (free tier) | Simples para cron jobs | Limitado para DAGs complexos |
| **Databricks Workflows** | Incluído nos DBUs | Nativo, já usado | Só orquestra dentro do Databricks |

**Recomendação**: Para o escopo atual (poucos DAGs, orquestração simples), **Databricks Workflows** já cobre a maioria dos casos. Para orquestração de ECS tasks e infra AWS, avaliar **Step Functions** como substituto do Airflow, eliminando a necessidade de hospedar Airflow em PROD.

### 6.5 VPC & Networking

| Item | Status | Ação |
|------|--------|------|
| EIP ociosa `ChainExplorer-nat-eip` | ✅ **Removida** (17/Mar/2026) | Economia: $3.60/mês |
| NAT Gateway | Não existe (design correto) | Manter sem NAT |
| S3 VPC Endpoint (Gateway) | ✅ Configurado | $0 — manter |
| Public IPs ECS Fargate | Em uso | Considerar PrivateLink se volume crescer |

### 6.6 S3 — Storage

| Bucket | Lifecycle | Status |
|--------|-----------|--------|
| `dm-chain-explorer-raw-data` | IA 30d → Glacier 90d | ✅ Já configurado |
| `dm-chain-explorer-lakehouse` | Nenhum | ⚠️ Adicionar lifecycle para dados antigos |
| `dm-chain-explorer-databricks` | Nenhum | ⚠️ Adicionar lifecycle para checkpoints antigos |
| `dm-chain-explorer-hml-ingestion` | Expire 7d | ✅ Já configurado |

---

## 7. Standby / Resume — Pausar PROD sem Perder Dados

O projeto já possui scripts de standby/resume (`scripts/prod_standby.sh`).

### O que acontece ao pausar:

| Recurso | Ação no Standby | Perda de Dados? | Custo Parado |
|---------|-----------------|-----------------|--------------|
| ECS Services | `desired_count=0` | ❌ Nenhuma (stateless) | $0 |
| Databricks Cluster | Auto-terminate (60 min) | ❌ Nenhuma (dados no S3) | $0 DBU, $0 EC2 |
| SQL Warehouse | Stop (manual ou auto-stop) | ❌ Nenhuma | $0 |
| DLT Pipeline | Stop | ❌ Checkpoints preservados no S3 | $0 |
| Kinesis Streams | **Continua rodando** | ❌ Dados preservados (24h retenção) | ~$3-8/mês |
| SQS/Firehose/CW | **Continua rodando** | ❌ Dados preservados | ~$1-3/mês |
| DynamoDB | **Continua rodando** | ❌ Dados preservados | ~$0.15/mês |
| S3 | **Continua rodando** | ❌ Dados preservados | ~$1.50/mês |

### Para economia máxima em standby:

1. Rodar `make prod_standby` (ECS → 0, Databricks clusters → parados)
2. **Opcional — agressivo**: Destruir Kinesis + Firehose via Terraform
   - Economia adicional: ~$6-16/mês
   - ⚠️ Perda: dados em trânsito nos streams (reconstruíveis)
   - Recriação: `terraform apply` no módulo 3_kinesis_sqs

### Custo mínimo de standby (apenas recursos persistentes):

| Recurso | Custo/Mês |
|---------|-----------|
| S3 (storage) | ~$1.50 |
| DynamoDB | ~$0.15 |
| Route 53 | ~$0.50 |
| ECR | ~$0.03 |
| **Total standby** | **~$2.18/mês** |

> Se destruir Kinesis/Firehose, o custo cai de ~$6-16/mês para ~$2.18/mês.

---

## 8. TODO — Roadmap de Otimização

### 🔴 Prioridade Alta (impacto > $30/mês)

- [x] **Migrar MSK → Kinesis/SQS/Firehose** — economia de ~$30-60/mês em PROD 24/7. ~~MSK Serverless~~ removido.
- [x] **Usar Spot instances** no Databricks cluster (`availability = "SPOT"`) — economia de 60-90% em EC2
- [x] **DLT scheduled** em vez de continuous — economia de ~$313/mês (de $375 para $62)
- [ ] **Serverless SQL Warehouse** para dashboards — paga $0 quando sem queries ativas

### 🟡 Prioridade Média (impacto $5-30/mês)

- [ ] **Ativar tags no Cost Explorer** — habilitar `cost-center`, `environment`, `project`, `deploy-id`
- [ ] **Reduzir réplicas** `mined_txs_crawler` de 8 → 4 (testar throughput) — economia ~$11/mês
- [ ] **Lifecycle S3** nos buckets `lakehouse` e `databricks` — IA 90d para dados antigos
- [ ] **Avaliar Step Functions** como substituto do Airflow para orquestração PROD
- [x] ~~**Right-size ElastiCache**~~ — eliminado (DynamoDB substitui completamente)
- [ ] **Habilitar Photon** nos pipelines DLT — processamento mais rápido = menos DBUs

### 🟢 Prioridade Baixa (melhoria contínua)

- [ ] **Cluster policies** no Databricks — limitar instance types e max workers
- [ ] **Instance pools** no Databricks — reduzir cold-start time
- [ ] **Budget alerts** no AWS — configurar alertas quando custo exceder threshold
- [ ] **Databricks Budgets API** — monitorar consumo de DBUs programaticamente
- [x] ~~**Consolidar ElastiCache → DynamoDB**~~ — ElastiCache removido, DynamoDB cobre todos os use cases
- [ ] **ECR lifecycle policy** — remover imagens antigas automaticamente
- [ ] **Reserved capacity** — considerar se o projeto rodar 24/7 estável por > 6 meses

---

## 9. Referências

- [Databricks Pricing (AWS)](https://www.databricks.com/product/aws-pricing)
- [Delta Live Tables Pricing](https://www.databricks.com/product/pricing/delta-live)
- [Best Practices for Cost Management on Databricks](https://www.databricks.com/blog/best-practices-cost-management-databricks)
- [AWS Kinesis Pricing](https://aws.amazon.com/kinesis/data-streams/pricing/)
- [AWS Firehose Pricing](https://aws.amazon.com/firehose/pricing/)
- [AWS ECS Fargate Pricing](https://aws.amazon.com/fargate/pricing/)
- [AWS Cost Allocation Tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- [Databricks System Tables — Billing](https://docs.databricks.com/aws/en/admin/system-tables/billing)
