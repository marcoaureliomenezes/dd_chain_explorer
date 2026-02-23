# dd-chain-explorer

Pipeline de dados para extração, processamento e análise de transações on-chain da rede Ethereum. O sistema captura dados da blockchain em tempo real via APIs de nós Ethereum, os processa em streaming com Delta Live Tables no Databricks e disponibiliza os dados em um lakehouse Delta organizado nas camadas Bronze, Silver e Gold.

---

## Sumário

- [Objetivo](#objetivo)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Quick Start — DEV](#quick-start--dev)
- [Deploy em Produção](#deploy-em-produção)
- [Makefile — Referência](#makefile--referência)
- [Documentação](#documentação)

---

## Objetivo

Extrair e enriquecer dados de blocos e transações da blockchain Ethereum para análise, com foco em:

- Monitoramento de blocos minerados e detecção de blocos órfãos em tempo real
- Captura completa de transações via APIs Alchemy e Infura
- Identificação de contratos mais utilizados (por volume de transações)
- Ingestão histórica de transações de contratos populares via Etherscan
- Disponibilização dos dados processados em tabelas Delta (Silver/Gold) no Unity Catalog

---

## Arquitetura

```
Blockchain (Ethereum Mainnet)
         │   APIs (Alchemy / Infura)
         ▼
   ┌─────────────┐
   │ ECS Fargate  │  4 apps Python (PROD)
   │              │  Docker Compose (DEV)
   └──────┬───────┘
          │ Kafka (MSK em PROD / local em DEV)
          ▼
   ┌─────────────────────────────────┐
   │  Databricks                     │
   │  Delta Live Tables (streaming)  │  5 pipelines contínuos
   │  ─────────────────────────────  │
   │  Bronze → Silver                │
   │  Workflows Batch                │  DDL · Periódico · Manutenção
   └─────────────────────────────────┘
          │
          ▼
   Unity Catalog (Delta Lake)
   b_fast · bronze · s_apps · s_logs · gold
```

---

## Tecnologias

| Categoria | Tecnologia |
|-----------|-----------|
| Cloud | AWS (`sa-east-1`) |
| IaC | Terraform >= 1.3 (7 módulos) |
| Mensageria | Amazon MSK (Kafka) + AWS Glue Schema Registry |
| Processamento streaming | Databricks Delta Live Tables |
| Processamento batch | Databricks Workflows |
| Armazenamento | Amazon S3 + Delta Lake (Unity Catalog) |
| Apps de captura | Python 3.10, `web3.py`, `confluent-kafka`, `boto3` |
| Containerização | Docker · ECS Fargate |
| Deploy Databricks | Databricks Asset Bundles (DABs) + CLI |
| CI/CD | GitHub Actions (3 workflows) |
| Gerenciamento de API keys | Amazon DynamoDB (tabelas on-demand) |

---

## Estrutura do Projeto

```
dd_chain_explorer/
├── dabs/                        # Databricks Asset Bundles
│   ├── databricks.yml           # Bundle root — targets: dev + prod
│   ├── resources/
│   │   ├── dlt/                 # 5 pipelines DLT (streaming Bronze + Silver)
│   │   └── workflows/           # 4 workflows batch
│   └── src/
│       ├── streaming/           # Notebooks DLT
│       └── batch/               # Notebooks DDL, periódico, manutenção
│
├── docker/
│   ├── onchain-stream-txs/      # 4 apps Python de captura contínua
│   └── onchain-batch-txs/       # App de ingestão batch + manutenção Kafka/S3
│
├── services/compose/
│   ├── local_services.yml       # Kafka + DynamoDB local (DEV)
│   ├── python_streaming_apps_layer.yml  # Apps Python em DEV
│   └── conf/                    # Variáveis de ambiente DEV
│
├── terraform_prd/               # Infra PRD: 9 módulos (S3 state → VPC → IAM → MSK → S3 → ElastiCache → ECS → Databricks → Glue)
│   └── [0-9]_*/                 #   Destruir tudo: make prod_destroy_infra
│
├── terraform_dev/               # Infra DEV: Databricks Free Edition
│   └── *.tf                     #   Criar: make dev_tf_apply | Destruir: make dev_tf_destroy
│
├── docs/to-be/                  # Documentação técnica completa ← ver abaixo
└── Makefile                     # Atalhos para todas as operações
```

---

## Quick Start — DEV

### Pré-requisitos

```bash
docker --version && docker compose version   # Docker >= 24, Compose v2
databricks --version                         # Databricks CLI >= 0.218.0
```

### 1. Infraestrutura local

```bash
docker network create vpc_dm
make deploy_dev_infra          # Kafka + Schema Registry + DynamoDB local
```

### 2. Criar tópicos Kafka

```bash
docker compose -f services/compose/python_streaming_apps_layer.yml \
  run --rm onchain-batch-txs \
  python /app/kafka_maintenance/0_create_topics.py
```

### 3. Apps Python de captura

```bash
make deploy_dev_stream         # sobe os 4 serviços de captura on-chain
```

### 4. DABs no Databricks Free Edition

```bash
# Configure dev_workspace_host em dabs/databricks.yml
make dabs_validate
make dabs_deploy_dev
make dabs_run_dev JOB=dm-ddl-setup      # cria todas as tabelas
```

> Guia completo: [docs/to-be/infrastructure/dev_environment.md](docs/to-be/infrastructure/dev_environment.md)

---

## Deploy em Produção

O deploy em PROD é automatizado via **GitHub Actions** com aprovação manual obrigatória (GitHub Environment `production`):

| Workflow | Trigger | O que faz |
|----------|---------|-----------|
| `deploy_infrastructure.yml` | Push em `terraform_prd/**` | `terraform plan` + `terraform apply` por módulo |
| `deploy_databricks.yml` | Push em `dabs/**` | `databricks bundle validate` + `bundle deploy --target prod` |
| `deploy_apps.yml` | Push em `docker/**` | Build das imagens → push DockerHub → update ECS task definitions |

```bash
# Fluxo padrão
git checkout -b feature/minha-alteracao
# desenvolver + testar em DEV
git push origin feature/minha-alteracao
# → Pull Request → aprovação → merge em main → CI/CD executa automaticamente
```

> Detalhes completos: [docs/to-be/gitflow.md](docs/to-be/gitflow.md)

---

## Makefile — Referência

### DEV — Infraestrutura local

```bash
make deploy_dev_infra          # Kafka + DynamoDB local
make stop_dev_infra            # Para infraestrutura
make deploy_dev_stream         # Apps Python de captura
make stop_dev_stream           # Para apps Python
```

### DABs — Databricks

```bash
make dabs_validate             # Valida o bundle
make dabs_deploy_dev           # Deploy em DEV
make dabs_deploy_prod          # Deploy em PROD (manual)
make dabs_run_dev JOB=<nome>   # Executa workflow em DEV
make dabs_status_dev           # Status dos recursos em DEV
```

Nomes de jobs disponíveis: `dm-ddl-setup`, `dm-periodic-processing`, `dm-iceberg-maintenance`, `dm-teardown`

### Terraform

```bash
make tf_init_all               # Init de todos os módulos
make tf_plan_vpc && make tf_apply_vpc
make tf_plan_msk && make tf_apply_msk
```

---

## Documentação

| Documento | Conteúdo |
|-----------|---------|
| [gitflow.md](docs/to-be/gitflow.md) | Gitflow e os 3 pipelines de CI/CD (GitHub Actions) |
| [infrastructure/dev_environment.md](docs/to-be/infrastructure/dev_environment.md) | Ambiente DEV local: Docker Compose, tópicos Kafka, DABs |
| [infrastructure/prod_environment.md](docs/to-be/infrastructure/prod_environment.md) | Infraestrutura PROD: todos os 7 módulos Terraform, ECS, MSK, DynamoDB, Databricks |
| [application/data_capture.md](docs/to-be/application/data_capture.md) | Apps Python: `mined_blocks_watcher`, `block_data_crawler`, `mined_txs_crawler`, `batch_ingestion` |
| [application/data_processing_stream.md](docs/to-be/application/data_processing_stream.md) | 5 pipelines DLT: schemas das tabelas Bronze e Silver |
| [application/data_processing_batch.md](docs/to-be/application/data_processing_batch.md) | 4 workflows batch: DDL, periódico (Etherscan), manutenção (OPTIMIZE/VACUUM) |
| [workflows/dlts.md](docs/to-be/workflows/dlts.md) | Referência rápida dos DLT pipelines |
| [workflows/jobs.md](docs/to-be/workflows/jobs.md) | Referência rápida dos Databricks Workflows |
