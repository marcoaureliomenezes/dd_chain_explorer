# Data Master On-premises — Documentação

## Visão Geral

O **Data Master On-premises** é um pipeline de dados de ponta a ponta para captura, processamento e análise de dados da blockchain Ethereum em tempo real e batch.

O projeto captura dados diretamente da blockchain via **Web3.py** (Alchemy/Infura), processa-os com **Apache Spark Streaming** e os armazena em um **Data Lakehouse** baseado em **Apache Iceberg**, **Nessie** e **MinIO**. A orquestração é feita com **Apache Airflow**.

---

## Arquitetura de Alto Nível

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         DATA MASTER ON-PREMISES                                │
│                                                                                │
│  FONTE DE DADOS                                                                │
│  Blockchain Ethereum (Mainnet)                                                 │
│       │                                                                        │
│       ├──── Web3.py (Alchemy/Infura) ──→ Jobs Python Streaming               │
│       │                                       │                                │
│       └──── Etherscan API ──────────→ Jobs Python Batch                       │
│                                               │                                │
│  ─────────────────────────────────────────────────────────────────────────    │
│  CAMADA DE MENSAGERIA                         │                                │
│  Kafka (Confluent) + Schema Registry          │                                │
│  └── Tópicos: logs, blocos, transações ◄──────┘                               │
│            │                                                                   │
│  ─────────────────────────────────────────────────────────────────────────    │
│  PROCESSAMENTO                                │                                │
│  Apache Spark Streaming ◄─────────────────────┘                               │
│  └── Bronze: landing zone raw (Iceberg)                                       │
│  └── Silver: dados parseados (Iceberg)                                        │
│            │                                                                   │
│  Apache Spark Batch                                                            │
│  └── Gold: agregações e views analíticas                                      │
│            │                                                                   │
│  ─────────────────────────────────────────────────────────────────────────    │
│  ARMAZENAMENTO (LAKEHOUSE)                    │                                │
│  MinIO (S3) + Nessie (catálogo) + Iceberg ◄──┘                               │
│            │                                                                   │
│  ─────────────────────────────────────────────────────────────────────────    │
│  CONSULTA ANALÍTICA                                                            │
│  Dremio (SQL) + JupyterLab                                                     │
│            │                                                                   │
│  ─────────────────────────────────────────────────────────────────────────    │
│  ORQUESTRAÇÃO                                                                  │
│  Apache Airflow (DAGs de criação, manutenção, monitoramento)                  │
│                                                                                │
│  ─────────────────────────────────────────────────────────────────────────    │
│  OBSERVABILIDADE                                                               │
│  Prometheus + Grafana + cAdvisor + Kafka Exporter                             │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Índice de Documentação

### Infraestrutura

| Documento | Descrição |
|-----------|-----------|
| [Infraestrutura Docker Compose](service/infra_compose.md) | Definição dos serviços para o ambiente de desenvolvimento local |
| [Infraestrutura Docker Swarm](service/infra_swarm.md) | Definição dos serviços para o ambiente de produção em cluster |

### Camada de Aplicação

| Documento | Descrição |
|-----------|-----------|
| [Infraestrutura de Serviços](app_layer/infra_servicos.md) | Imagens Docker, lib `dm-33-utils` e serviços periféricos |
| [Jobs Python Streaming](app_layer/python_stream_jobs.md) | Captura em tempo real de blocos e transações da Ethereum |
| [Jobs Python Batch](app_layer/python_batch_jobs.md) | Captura periódica de transações de contratos via Etherscan API |
| [Jobs Spark Streaming](app_layer/spark_stream_jobs.md) | Processamento em tempo real: Bronze e Silver Iceberg |
| [Jobs Spark Batch](app_layer/spark_batch_jobs.md) | DDL, processamento periódico e manutenção do Data Lake |

### Arquitetura de Dados

| Documento | Descrição |
|-----------|-----------|
| [Arquitetura Lakehouse](lakehouse.md) | MinIO, Nessie, Spark, Dremio e camadas Bronze/Silver/Gold |
| [Orquestração — Airflow](orchestration.md) | DAGs, agendamentos e operadores Docker |

---

## Topologia de Tópicos Kafka

| Tópico                             | Produtores                      | Consumidores                        | Dados                              |
|------------------------------------|---------------------------------|-------------------------------------|------------------------------------|
| `mainnet.0.application.logs`       | Todos os jobs Python streaming  | Spark `1_api_key_monitor.py`        | Logs estruturados de aplicações    |
| `mainnet.0.batch.logs`             | Jobs Python batch               | Spark `2_job_bronze_multiplex.py`   | Logs de jobs batch                 |
| `mainnet.1.mined_blocks.events`    | `1_mined_blocks_watcher.py`     | `3_block_data_crawler.py`, Spark    | Eventos: bloco_number, hash, ts    |
| `mainnet.2.blocks.data`            | `3_block_data_crawler.py`       | Spark `5_job_silver_blocks.py`      | Dados completos dos blocos         |
| `mainnet.3.block.txs.hash_id`      | `3_block_data_crawler.py`       | `4_mined_txs_crawler.py`            | Hashes de transações por bloco     |
| `mainnet.4.transactions.data`      | `4_mined_txs_crawler.py`        | Spark `6_job_silver_transactions.py`| Dados completos de transações      |

---

## Tabelas do Data Lake

| Tabela                              | Camada  | Tipo   | Jobs que escrevem              |
|-------------------------------------|---------|--------|--------------------------------|
| `b_fast.kafka_topics_multiplexed`   | Bronze  | Iceberg| Spark Streaming (multiplex)    |
| `bronze.popular_contracts_txs`      | Bronze  | Iceberg| Spark Batch (ingestão batch)   |
| `s_apps.mined_blocks_events`        | Silver  | Iceberg| Spark Streaming                |
| `s_apps.blocks_fast`                | Silver  | Iceberg| Spark Streaming                |
| `s_apps.blocks_txs_fast`            | Silver  | Iceberg| Spark Streaming                |
| `s_apps.transactions_fast`          | Silver  | Iceberg| Spark Streaming                |
| `s_logs.apps_logs_fast`             | Silver  | Iceberg| Spark Streaming                |
| `gold.*`                            | Gold    | Views  | Spark Batch (DDL)              |

---

## Mapa de Migração para a Cloud

| Componente On-premises             | Equivalente Cloud (AWS + Databricks)               |
|------------------------------------|-----------------------------------------------------|
| Docker Swarm                       | Amazon ECS Fargate / EKS                           |
| Kafka + ZooKeeper + Schema Registry | Amazon MSK + AWS Glue Schema Registry             |
| Redis                              | Amazon ElastiCache for Redis                        |
| MinIO (Object Storage)             | Amazon S3                                           |
| Nessie (Iceberg Catalog)           | Databricks Unity Catalog                            |
| Dremio (SQL Engine)                | Databricks SQL Warehouse                            |
| Apache Spark Standalone            | Databricks Runtime (gerenciado/serverless)          |
| Apache Airflow                     | Databricks Workflows / AWS MWAA                     |
| Prometheus + Grafana               | AWS CloudWatch + Managed Grafana                    |
| Azure Key Vault                    | AWS Secrets Manager                                 |
| Docker Hub                         | Amazon ECR (Elastic Container Registry)             |
| Jobs Python (Docker local)         | Amazon ECS (Fargate tasks)                          |

---

## Estrutura do Repositório

```
dd_chain_explorer/
├── Makefile                        # Comandos de build, deploy e operação
├── docker/
│   ├── app_layer/                  # Código fonte das aplicações
│   │   ├── onchain-batch-txs/      # Jobs Python Batch
│   │   ├── onchain-stream-txs/     # Jobs Python Streaming
│   │   ├── spark-batch-jobs/       # Jobs Spark Batch
│   │   └── spark-streaming-jobs/   # Jobs Spark Streaming
│   └── customized/                 # Imagens customizadas de serviços
│       ├── airflow/
│       ├── jupyterlab/
│       ├── spark/
│       └── prometheus/
├── services/
│   ├── compose/                    # Docker Compose (desenvolvimento)
│   └── swarm/                      # Docker Swarm (produção)
├── mnt/
│   └── airflow/
│       └── dags/                   # DAGs do Airflow
├── docs/                           # Esta documentação
└── scripts/                        # Scripts de configuração do cluster

lib-dm-utils/                       # Biblioteca Python interna
└── dm_33_utils/                    # Módulos utilitários
    ├── web3_utils.py
    ├── etherscan_utils.py
    ├── kafka_utils.py
    ├── schema_reg_utils.py
    ├── logger_utils.py
    └── spark_utils.py
```

---

## Pré-requisitos para Execução

### Ambiente de Desenvolvimento (Docker Compose):

1. Docker e Docker Compose instalados
2. Rede Docker `vpc_dm` criada: `docker network create vpc_dm`
3. Arquivo `services/compose/conf/swarm.secrets.conf` com as credenciais
4. Credenciais Azure (para Azure Key Vault) configuradas

```bash
# Subir ambiente de desenvolvimento
make deploy_dev_apps          # Apps Python Streaming
make deploy_dev_airflow       # Airflow
```

### Ambiente de Produção (Docker Swarm):

1. Cluster Swarm configurado com 4 nós
2. NFS configurado em `/mnt/nfs/swarm/` em todos os nós
3. Rede overlay `vpc_dm` criada no Swarm
4. Imagens publicadas no Docker Hub

```bash
# Configurar e iniciar cluster
make preconfig_cluster_swarm
make start_cluster_swarm

# Build e publish das imagens
make build_apps && make publish_apps
make build_airflow && make publish_customized

# Deploy de todas as stacks
make deploy_prod_all
make deploy_prod_airflow
make deploy_prod_spark_apps
```
