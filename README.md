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
         │   APIs (Alchemy / Infura / Etherscan)
         ▼
   ┌──────────────────┐     ┌───────────────────────┐
   │ ECS Fargate       │     │ Lambda                 │
   │ 5 apps Python     │     │ contracts-ingestion    │
   │ (streaming)       │     │ (hourly, EventBridge)  │
   └──────┬────────────┘     └──────────┬────────────┘
          │ Kinesis/SQS/Firehose        │ S3 (batch/)
          ▼                             ▼
   ┌─────────────────────────────────────────────┐
   │  Databricks                                  │
   │  Delta Live Tables (streaming)  │  DLT Auto  │
   │  ─────────────────────────────  │  Loader    │
   │  Bronze → Silver → Gold                      │
   │  Workflows (schedules nativos)               │
   └──────────────────────────────────────────────┘
          │
          ▼
   Unity Catalog (Delta Lake)
   b_ethereum · b_app_logs · s_apps · s_logs · gold
```

---

## Tecnologias

| Categoria | Tecnologia |
|-----------|-----------|
| Cloud | AWS (`sa-east-1`) |
| IaC | Terraform >= 1.3 (7 módulos) |
| Mensageria | AWS Kinesis Data Streams + SQS + Firehose |
| Processamento streaming | Databricks Delta Live Tables (Auto Loader) |
| Processamento batch | Databricks Workflows (schedules nativos) |
| Ingestão batch | AWS Lambda + EventBridge Scheduler |
| Armazenamento | Amazon S3 + Delta Lake (Unity Catalog) |
| Apps de captura | Python 3.12, `web3.py`, `boto3` |
| Containerização | Docker · ECS Fargate |
| Deploy Databricks | Databricks Asset Bundles (DABs) + CLI |
| CI/CD | GitHub Actions |
| State management | Amazon DynamoDB (single-table, on-demand) |

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
│   └── onchain-stream-txs/      # 5 apps Python de captura contínua (streaming)
│
├── lambda/
│   └── contracts_ingestion/     # Lambda: Etherscan → S3 (hourly, EventBridge)
│
├── scripts/
│   └── environment/             # cleanup_s3.py, cleanup_dynamodb.py
│
├── services/
│   ├── dev/compose/             # local_services.yml, app_services.yml
│   └── prd/                     # Terraform PRD: 10 módulos
│
├── utils/
│   └── src/dm_chain_utils/      # Biblioteca Python compartilhada
│
├── docs/                        # Documentação técnica completa
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
make deploy_dev_infra          # Rede Docker vpc_dm + serviços locais
```

### 2. Apps Python de captura (streaming)

```bash
make deploy_dev_stream         # sobe os 5 serviços de captura on-chain
```

### 3. DABs no Databricks Free Edition

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
make deploy_dev_infra          # Rede Docker + serviços locais
make stop_dev_infra            # Para infraestrutura
make deploy_dev_stream         # Apps Python de captura (streaming)
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

Nomes de jobs disponíveis: `dm-ddl-setup`, `dm-periodic-processing`, `dm-iceberg-maintenance`, `dm-teardown`, `dm-trigger-dlt-all`

### Terraform

```bash
make tf_init_prd               # Init de todos os módulos PRD
make tf_apply_free_resources   # VPC + IAM + S3 (custo zero)
make tf_apply_databricks       # Databricks workspace
```

---

## Documentação

| Documento | Conteúdo |
|-----------|---------|
| [01_architecture.md](docs/01_architecture.md) | Arquitetura geral: captura, streaming, processamento, orquestração |
| [02_data_capture.md](docs/02_data_capture.md) | Apps Python de streaming + Lambda batch + scripts de ambiente |
| [03_data_processing.md](docs/03_data_processing.md) | DLT pipelines: schemas Bronze, Silver, Gold |
| [04_data_ops.md](docs/04_data_ops.md) | CI/CD, deploy, monitoramento |
| [05_data_serving.md](docs/05_data_serving.md) | Dashboards e APIs |
| [06_fin_ops.md](docs/06_fin_ops.md) | Análise de custos AWS + Databricks |
| [07_roadmap.md](docs/07_roadmap.md) | Roadmap e TODOs por área |
| [rearchitecting_airflow.md](docs/rearchitecting_airflow.md) | Plano de migração Airflow → Databricks Workflows + Lambda |
