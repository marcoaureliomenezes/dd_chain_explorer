# 01 — Arquitetura do DD Chain Explorer

## Visão Geral

O **DD Chain Explorer** é uma plataforma de engenharia de dados em tempo real para extração, processamento e análise de transações e blocos da blockchain Ethereum. A arquitetura segue um modelo de ingestão em camadas:

1. **Captura on-chain** — Serviços Python containerizados que extraem dados da Ethereum via APIs Web3 (Alchemy/Infura) e publicam em Kinesis Data Streams (dados) ou SQS (coordenação inter-job).
2. **Streaming & Ingestão** — Kinesis Firehose entrega NDJSON no S3; CloudWatch Logs + Firehose entrega logs de aplicação no S3.
3. **Processamento analítico** — Delta Live Tables (DLT) no Databricks com Auto Loader (`cloudFiles`) lendo NDJSON do S3, implementando arquitetura medalhão (Bronze → Silver → Gold).
4. **Orquestração** — Databricks Workflows (schedules nativos) para pipelines DLT e jobs batch. Lambda + EventBridge para ingestão Etherscan → S3.

```
Ethereum Mainnet
    │  (RPC via Alchemy/Infura)
    ▼
┌──────────────────────────────────────────┐
│  CAMADA DE CAPTURA (5 Jobs Python)       │
│  ├─ 1_mined_blocks_watcher              │
│  ├─ 2_orphan_blocks_watcher             │
│  ├─ 3_block_data_crawler                │
│  ├─ 4_mined_txs_crawler (6 réplicas)    │
│  └─ 5_txs_input_decoder                 │
└──────────────┬───────────────────────────┘
               │
    ┌──────────┼────────────────────┐
    ▼          ▼                    ▼
┌────────┐ ┌────────┐ ┌──────────────────┐
│  SQS   │ │Kinesis │ │ CloudWatch Logs   │
│(coord) │ │(dados) │ │  (app logs)       │
└────────┘ └───┬────┘ └────────┬─────────┘
               │               │
               ▼               ▼
         ┌──────────────────────────┐
         │  Kinesis Firehose → S3   │
         │  (NDJSON, particionado   │
         │   por hora)              │
         └────────────┬─────────────┘
                      ▼
┌──────────────────────────────────────────┐
│  DATABRICKS — Delta Live Tables          │
│  ├─ Bronze: Auto Loader (cloudFiles)     │
│  ├─ Silver: blocos, transações, logs     │
│  └─ Gold: contratos populares, gas, etc. │
└──────────────────────────────────────────┘
```

---

## Componentes Principais

### 1. Serviços de Captura (Streaming)

Cinco jobs Python executam em containers Docker e formam uma pipeline encadeada de extração de dados on-chain. Jobs de coordenação (1→2, 3→4) comunicam via SQS. Jobs de dados (2→Kinesis, 3→Kinesis, 4→Kinesis, 5→Kinesis) publicam registros JSON em Kinesis Data Streams, que são entregues no S3 pelo Firehose como NDJSON.

- **Job 1 (Mined Blocks Watcher)**: Detecta blocos recém-minerados via polling RPC. Publica evento em SQS.
- **Job 2 (Orphan Blocks Watcher)**: Consome SQS, verifica finalidade de blocos e detecta reorganizações (reorgs) usando cache DynamoDB. Produz dados de blocos em Kinesis.
- **Job 3 (Block Data Crawler)**: Busca dados completos de blocos e distribui hashes de transações em SQS.
- **Job 4 (Mined Txs Crawler)**: Consome SQS, busca dados brutos de transações com **6 réplicas** usando rotação distribuída de API keys via semáforo DynamoDB. Produz em Kinesis.
- **Job 5 (Txs Input Decoder)**: Consome Kinesis, decodifica o campo `input` de transações usando ABIs do Etherscan, 4byte.directory e cache DynamoDB. Produz em Kinesis.

Todos os jobs enviam logs estruturados para CloudWatch Logs, que são entregues no S3 pelo Firehose.

Um job periódico no Databricks exporta métricas Gold de consumo de API keys para S3, onde uma Lambda sincroniza com o DynamoDB.

### 2. Mensageria AWS (Kinesis / SQS / CloudWatch Logs)

Substituem o Apache Kafka como barramento de eventos. Dados fluem como JSON nativo (sem Avro/Schema Registry).

| Serviço | Recurso | Descrição |
|---------|---------|----------|
| **CloudWatch Logs** | `/apps/dm-chain-explorer-{env}` | Logs estruturados de todos os jobs → Firehose → S3 (`raw/app_logs/`) |
| **SQS** | `mainnet-mined-blocks-events-{env}` | Coordenação Job 1 → Job 2 (eventos de blocos minerados) |
| **Kinesis** | `mainnet-blocks-data-{env}` | Dados completos de blocos → Firehose → S3 (`raw/mainnet-blocks-data/`) |
| **SQS** | `mainnet-block-txs-hash-id-{env}` | Coordenação Job 3 → Job 4 (hashes de transações) |
| **Kinesis** | `mainnet-transactions-data-{env}` | Dados brutos de transações → Firehose → S3 (`raw/mainnet-transactions-data/`) |
| **Kinesis** | `mainnet-transactions-decoded-{env}` | Transações com input decodificado → Firehose → S3 (`raw/mainnet-transactions-decoded/`) |

### 3. Kinesis Firehose (S3 Delivery)

Firehose consome dos Kinesis Data Streams e CloudWatch Logs e entrega arquivos NDJSON no S3, particionados por hora:

- **Dados de streams**: `s3://{ingestion-bucket}/raw/{stream-name}/year=YYYY/month=MM/day=DD/hour=HH/`
- **App logs**: `s3://{ingestion-bucket}/raw/app_logs/year=YYYY/month=MM/day=DD/hour=HH/`
- Buffer: 1 MB ou 60s (o que ocorrer primeiro)

### 4. Databricks (DLT)

Processamento analítico implementado com Delta Live Tables seguindo arquitetura medalhão:

- **Bronze**: Auto Loader (`cloudFiles`) lê NDJSON do S3 (entrega Firehose). Uma tabela bronze por stream.
- **Silver**: Parse JSON, limpeza, enriquecimento e joins stream-static.
- **Gold**: Materialized views — contratos populares, transações P2P, consumo de gas, consumo de API keys.

### 5. Orquestração (Databricks Workflows + Lambda)

A orquestração é feita nativamente pelo Databricks Workflows (schedules Quartz cron) e AWS Lambda + EventBridge:

- **A cada 5 min**: Workflow consolidado `dm-trigger-dlt-all` dispara pipelines DLT Ethereum → App Logs sequencialmente.
- **A cada hora**: Lambda `contracts-ingestion` captura transações de contratos populares via Etherscan API → S3. Workflow `dm-periodic-processing` processa S3 → Bronze → Silver → Gold.
- **A cada 12h**: Workflow `dm-iceberg-maintenance` executa OPTIMIZE + VACUUM nas tabelas.
- **Eventual (manual)**: Workflows `dm-ddl-setup` (criação de tabelas), `dm-teardown` (remoção), `dm-dlt-full-refresh` (reprocessamento completo).
- **Limpeza de ambiente**: Scripts standalone `scripts/environment/cleanup_s3.py` e `cleanup_dynamodb.py`.

---

## Ambientes: DEV vs PROD

### Correlação de Componentes

| Componente | DEV (Local) | PROD (AWS) |
|------------|-------------|------------|
| **Kinesis Data Streams** | AWS Kinesis (on-demand, `-dev` suffix) | AWS Kinesis (on-demand, `-prd` suffix) |
| **SQS** | AWS SQS (`-dev` suffix) | AWS SQS (`-prd` suffix) |
| **CloudWatch Logs** | AWS CloudWatch (`/apps/dm-chain-explorer-dev`) | AWS CloudWatch (`/apps/dm-chain-explorer-prd`) |
| **Firehose** | AWS Firehose → S3 DEV bucket | AWS Firehose → S3 lakehouse bucket |
| **DynamoDB** | AWS DynamoDB (single-table `dm-chain-explorer`, credenciais ~/.aws) | AWS DynamoDB (single-table `dm-chain-explorer`, IAM task role) |
| **Jobs Python (streaming)** | Docker Compose na rede `vpc_dm` | ECS Fargate (5 services, awsvpc mode) |
| **Databricks** | Free Edition (Community Cloud) | Workspace AWS (Terraform-provisioned, Unity Catalog) |
| **S3 Storage** | Bucket `dm-chain-explorer-dev-ingestion` | 3 buckets: raw, lakehouse, databricks |
| **Orquestração** | Databricks Workflows (schedules nativos) | Databricks Workflows + Lambda (EventBridge) |
| **API Keys** | AWS SSM Parameter Store (compartilhado) | AWS SSM Parameter Store (mesmo) |
| **Monitoramento** | CloudWatch Logs + Metrics | CloudWatch Logs + Metrics |

### Ambiente DEV — Topologia de Rede

O ambiente de DEV opera em **duas redes isoladas**:

**1. Rede local Docker (`vpc_dm`)**
```
┌─── Rede Docker: vpc_dm ────────────────────────────────────┐
│                                                             │
│  python-job-* (5 jobs streaming)                            │
│                                                             │
│  (jobs acessam AWS Kinesis/SQS/CloudWatch via boto3)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**2. Rede Databricks Free Edition (Cloud)**
- Workspace em `https://community.cloud.databricks.com` (ou `dbc-*.cloud.databricks.com`)
- Acessa dados via External Location no S3 (bucket DEV)
- DLT lê NDJSON do S3 via Auto Loader (dados entregues pelo Firehose)

### Ambiente PROD — Topologia de Rede

```
┌─── VPC: 172.31.0.0/16 (sa-east-1) ─────────────────────────────┐
│                                                                  │
│  ┌── Subnets Públicas (AZ a, b, c) ──────────────────────────┐  │
│  │  ECS Fargate Tasks (awsvpc, IP público)                    │  │
│  │  ├─ dm-mined-blocks-watcher                                │  │
│  │  ├─ dm-orphan-blocks-watcher                               │  │
│  │  ├─ dm-block-data-crawler                                  │  │
│  │  ├─ dm-mined-txs-crawler (6 réplicas)                      │  │
│  │  └─ dm-txs-input-decoder                                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  AWS Managed Services (regional, sem VPC):                       │
│  ├─ Kinesis Data Streams (3 streams on-demand)                   │
│  ├─ Kinesis Firehose (4 delivery streams → S3)                   │
│  ├─ SQS (2 filas + 2 DLQs)                                      │
│  └─ CloudWatch Logs (/apps/dm-chain-explorer-prd)                │
│                                                                  │
│  S3 VPC Endpoint (gateway) → acesso S3 sem sair da VPC          │
│                                                                  │
│  Security Groups:                                                │
│  └─ sg-ecs-tasks: permite saída HTTPS, entrada entre tasks      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─── Databricks Workspace ─────────────────────────────────────────┐
│  Unity Catalog: dd_chain_explorer                                │
│  Cluster: 1 worker, LTS Spark, auto-terminate 60 min            │
│  External Locations: raw S3, lakehouse S3, databricks S3         │
│  Acesso S3 via IAM (External Locations)                          │
└──────────────────────────────────────────────────────────────────┘
```

**Recursos Terraform (PROD)** — módulos em `services/prd/`, ordem de deploy `01→02→03→04→05→06+07`:
- **01_tf_state**: S3 backend + DynamoDB lock para state remoto
- **02_vpc**: VPC, subnets, IGW, security groups, S3 endpoint
- **03_iam**: Roles para ECS (execution + task), Databricks (cross-account + cluster)
- **04_peripherals**: Kinesis Data Streams, Firehose, SQS, CloudWatch Logs, S3 (raw/lakehouse/databricks), DynamoDB
- **05_databricks**: Workspace MWS, Unity Catalog, metastore, external locations, cluster
- **06_lambda**: Lambda gold_to_dynamodb (S3 event → DynamoDB sync) + Lambda contracts_ingestion (EventBridge hourly → Etherscan → S3)
- **07_ecs**: Cluster Fargate + task definitions + ECR repos

### Segurança

| Aspecto | DEV | PROD |
|---------|-----|------|
| **Kinesis/SQS/CW Auth** | Credenciais ~/.aws (perfil padrão) | IAM task role (ECS Fargate) |
| **Kinesis/SQS Encryption** | KMS (padrão do módulo) | KMS (padrão do módulo) |
| **DynamoDB** | Credenciais ~/.aws (perfil padrão) | IAM task role (ECS Fargate) |
| **API Keys** | SSM Parameter Store (AWS) | SSM Parameter Store (AWS) — compartilhado |
| **Databricks** | Personal Access Token (PAT) | Service Principal (OAuth M2M) |
| **ECS** | N/A | IAM roles (task execution + task role) |

---

## Referências de Arquivos

| Escopo | Arquivos |
|--------|----------|
| Jobs Streaming | `docker/onchain-stream-txs/src/1_*.py` a `5_*.py` |
| Jobs Batch (Lambda) | `lambda/contracts_ingestion/` |
| Docker Compose DEV | `services/dev/00_compose/app_services.yml` |
| Terraform DEV | `services/dev/01_peripherals/` (S3, Kinesis, SQS, DynamoDB, CloudWatch) + `services/dev/02_lambda/` (Lambda) |
| Terraform PRD | `services/prd/01_tf_state/` a `07_ecs/` |
| Shared Modules | `services/modules/` (s3, dynamodb, kinesis, sqs, lambda, ecs, iam, vpc, cloudwatch_logs) |
| DABs | `dabs/databricks.yml`, `dabs/resources/`, `dabs/src/` |
| Scripts Ambiente | `scripts/environment/` |
| CI/CD | `.github/workflows/` |
| Makefile | `Makefile` |
| Configs Compose | `services/dev/00_compose/conf/` |

---

## TODOs — Arquitetura

- [x] **TODO-A02**: ~~Resolver a ponte Kafka → S3 em PROD.~~ Resolvido pela migração Kinesis/Firehose → S3.
- [x] **TODO-A03**: ~~Definir estratégia de Airflow em PROD.~~ Resolvido — Airflow removido. Orquestração migrada para Databricks Workflows (schedules nativos) + Lambda (EventBridge). Ver `docs/rearchitecting_airflow.md`.
- [x] **TODO-A04**: ~~Implementar TLS para comunicação Kafka em PROD.~~ Eliminado — Kafka removido. Kinesis/SQS/CloudWatch usam TLS nativo via AWS SDK.
- [x] **TODO-A06**: ~~Implementar observabilidade em PROD.~~ CloudWatch Logs + Metrics nativos com a migração. Dashboards podem ser criados sobre CloudWatch.
- [ ] **TODO-A07**: Avaliar necessidade de NAT Gateway na VPC de PROD. Atualmente ECS tasks têm IP público para acesso à internet (APIs Web3). NAT Gateway é mais seguro, porém tem custo.
- [x] **TODO-A10**: ~~Criar ambiente de staging/homologação.~~ Resolvido — ambiente HML opera com recursos 100% efêmeros provisionados e destruídos dentro dos workflows de deploy de apps (`deploy_dm_applications.yml` — jobs `stream-hml-*`, `dabs-hml-*`, `lambda-hml-*`). Infra persistente de HML removida.
- [x] **TODO-A11**: ~~Substituir Spark Streaming Kafka→S3 por Kafka Connect S3 Sink.~~ Eliminado — Firehose entrega NDJSON no S3 nativamente. Spark Streaming removido.
- [ ] **TODO-A12**: Estudo de custo **ECS Fargate vs EC2/EKS**. Duplicar os services de streaming em um cluster EC2 (capacity provider) ou EKS, rodar ambos por 24h e comparar custos. Workload previsível (5 jobs + 6 réplicas do job 4) favorece EC2 com instâncias reservadas.
