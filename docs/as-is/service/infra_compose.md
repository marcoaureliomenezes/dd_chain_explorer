# Infraestrutura Docker Compose — Data Master On-premises

## 1. Visão Geral

O Docker Compose é utilizado como ambiente de **desenvolvimento e testes locais** do projeto. Ele espelha a mesma arquitetura em camadas do ambiente de produção (Docker Swarm), porém sem restrições de nós e sem os mecanismos de alta disponibilidade do Swarm.

Todos os arquivos de definição de serviços Docker Compose estão em:

```
dd_chain_explorer/services/compose/
├── batch_apps_layer.yml
├── orchestration_layer.yml
├── python_streaming_apps_layer.yml
├── spark_streaming_apps_layer.yml
└── conf/
    ├── dev.kafka.conf
    ├── dev.lakehouse.conf
    ├── dev.redis.conf
    ├── secrets_public.conf
    └── swarm.secrets.conf
```

A rede Docker virtual utilizada por todos os serviços é a `vpc_dm` (declarada como `external: true`), ou seja, deve ser criada previamente.

---

## 2. Arquivos de Configuração e Variáveis de Ambiente

Todos os serviços consomem variáveis de ambiente a partir de arquivos `.conf`:

| Arquivo                     | Propósito                                                      |
|-----------------------------|----------------------------------------------------------------|
| `conf/swarm.secrets.conf`   | Credenciais sensíveis (Azure KV, AWS keys, senhas)            |
| `conf/dev.kafka.conf`       | Endereços do broker Kafka e Schema Registry                   |
| `conf/dev.redis.conf`       | Host, porta e senha do Redis                                  |
| `conf/dev.lakehouse.conf`   | URLs do MinIO (S3), Nessie, configuração do Spark             |
| `conf/secrets_public.conf`  | Configurações públicas não sensíveis                          |

> **Nota Cloud:** No ambiente Cloud, essas variáveis serão injetadas via AWS Secrets Manager / Parameter Store, e os endpoints apontarão para serviços gerenciados (MSK, ElastiCache/CosmosDB, S3, Unity Catalog).

---

## 3. Camadas de Serviços

### 3.1 Camada de Aplicação — Jobs Batch Python (`batch_apps_layer.yml`)

Arquivo: `services/compose/batch_apps_layer.yml`

**Serviços definidos:**

| Serviço         | Imagem / Build                              | Função                                                         |
|-----------------|---------------------------------------------|----------------------------------------------------------------|
| `notebook`      | `docker/customized/jupyterlab`              | JupyterLab com Spark e Trino para análise exploratória         |
| `python-batch`  | `docker/app_layer/onchain-batch-txs`        | Captura batch de transações de contratos via Etherscan API     |
| `spark-batch`   | `docker/app_layer/spark-batch-jobs`         | Jobs Spark batch para processamento no Data Lake               |

**Variáveis de ambiente relevantes (python-batch):**

```yaml
environment:
  TOPIC_LOGS: mainnet.0.application.logs
  AKV_NAME: "DMEtherscanAsAService"
  APK_NAME: "etherscan-api-key-1"
  EXEC_DATE: "2025-02-01 00:00:00+00:00"
  S3_BUCKET: "raw-data"
  S3_BUCKET_PREFIX: "contracts_transactions"
```

O serviço `python-batch` utiliza a imagem `onchain-batch-txs`, que conecta-se à API da Etherscan para capturar transações de contratos populares e as ingerir em um bucket S3 (MinIO).

---

### 3.2 Camada de Aplicação — Jobs Stream Python (`python_streaming_apps_layer.yml`)

Arquivo: `services/compose/python_streaming_apps_layer.yml`

Utiliza uma âncora YAML (`x-conf-dev-onchain-stream-txs`) para compartilhar configurações comuns entre todos os jobs de streaming Python.

**Configuração compartilhada:**

```yaml
x-conf-dev-onchain-stream-txs: &conf_dev_onchain_stream_txs
  restart: on-failure
  env_file:
    - ./conf/swarm.secrets.conf
    - ./conf/dev.kafka.conf
    - ./conf/dev.redis.conf
  networks:
    - vpc_dm
  build: ../../docker/app_layer/onchain-stream-txs
  volumes:
    - ../../docker/app_layer/onchain-stream-txs/src:/app
```

**Serviços definidos (pipeline de streaming):**

| Serviço                            | Tópico Kafka Produzido                  | Descrição                                             |
|------------------------------------|-----------------------------------------|-------------------------------------------------------|
| `python-job-mined-blocks-watcher`  | `mainnet.1.mined_blocks.events`         | Observa a blockchain e publica eventos de novos blocos |
| `python-job-orphan-blocks-watcher` | `mainnet.1.mined_blocks.events`         | Detecta blocos órfãos (comentado / inativo)           |
| `python-job-block-data-crawler`    | `mainnet.2.blocks.data`, `mainnet.3.block.txs.hash_id` | Crawlea dados de bloco e hashes de transações (inativo) |
| `python-job-transactions_crawler`  | `mainnet.4.transactions.data`           | Crawlea dados completos de transações (inativo)       |
| `python-job-redis-collector`       | —                                       | Coleta semáforos do Redis (inativo)                   |

> Os serviços marcados como comentados/inativos representam o pipeline de streaming completo que é orquestrado no ambiente de produção (Swarm).

---

### 3.3 Camada de Processamento — Jobs Spark Streaming (`spark_streaming_apps_layer.yml`)

Arquivo: `services/compose/spark_streaming_apps_layer.yml`

Utiliza âncora YAML para configuração compartilhada dos jobs Spark Streaming.

**Serviços definidos:**

| Serviço                               | Script PySpark                          | Função                                                          |
|---------------------------------------|-----------------------------------------|-----------------------------------------------------------------|
| `spark-app-apk-comsumption`           | `1_api_key_monitor.py`                  | Consome logs do Kafka e escreve consumo de API Keys no Redis    |
| `spark-app-multiplex-bronze`          | `2_job_bronze_multiplex.py`             | Multiplexação de múltiplos tópicos Kafka em uma tabela Bronze   |
| `spark-app-silver-logs`               | `3_job_silver_apps_logs.py`             | Processa logs de aplicação do Bronze para Silver                |
| `spark-app-silver-mined-blocks-events`| `4_job_silver_blocks_events.py`         | Processa eventos de blocos minerados do Bronze para Silver      |
| `spark-app-silver-blocks`             | `5_job_silver_blocks.py`                | Processa dados de blocos do Bronze para Silver                  |
| `spark-app-silver-txs`                | `6_job_silver_transactions.py`          | Processa dados de transações do Bronze para Silver              |

**Tópicos Kafka consumidos pelo multiplex:**

```
mainnet.0.application.logs
mainnet.0.batch.logs
mainnet.1.mined_blocks.events
mainnet.2.blocks.data
mainnet.4.transactions.data
```

**Tabelas geradas:**

```
bronze.kafka_topics_multiplexed   → tabela Iceberg central de entrada
silver.app_logs_fast              → logs de aplicações
silver.mined_blocks_events        → eventos de blocos
silver.blocks                     → dados de blocos
silver.blocks_transactions        → hash IDs de transações por bloco
silver.transactions_fast          → dados completos de transações
```

---

### 3.4 Camada de Orquestração — Airflow (`orchestration_layer.yml`)

Arquivo: `services/compose/orchestration_layer.yml`

O Airflow é deployado com executor `LocalExecutor`, usando PostgreSQL como banco de metadados.

**Componentes:**

| Serviço               | Função                                                        |
|-----------------------|---------------------------------------------------------------|
| `airflow_pg`          | PostgreSQL 16 — banco de metadados do Airflow                 |
| `airflow-apiserver`   | API REST do Airflow (porta `8080`)                            |
| `airflow-scheduler`   | Agendador de DAGs                                             |
| `airflow-dag-processor`| Processador de arquivos de DAG                              |
| `airflow-init`        | Inicialização e migração do banco de dados do Airflow         |
| `airflow-cli`         | CLI do Airflow (perfil debug)                                 |

**Variáveis de ambiente críticas do Airflow:**

```yaml
AIRFLOW__CORE__EXECUTOR: LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow_pg/airflow
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
```

O serviço `airflow-init` verifica recursos mínimos (4 GB RAM, 2 CPUs, 10 GB disco) e migra o banco antes de iniciar os demais componentes.

---

## 4. Comandos Make — Docker Compose

Os comandos para gerenciamento do ambiente Docker Compose estão definidos no `Makefile`:

```makefile
# Deploy de serviços
make deploy_dev_apps        # Sobe streaming Python apps
make deploy_dev_airflow     # Sobe Airflow (orchestração)
make deploy_test_batch      # Sobe batch apps (Python + Spark)

# Parar serviços
make stop_dev_apps          # Para streaming Python apps
make stop_dev_airflow       # Para Airflow
make stop_test_batch        # Para batch apps
make stop_dev_all           # Para todos os serviços compose
```

---

## 5. Diagrama de Dependências — Docker Compose

```
┌─────────────────────────────────────────────────────────────────┐
│                     REDE: vpc_dm (external)                     │
│                                                                 │
│  ┌──────────────────────────────────┐                           │
│  │   batch_apps_layer.yml           │                           │
│  │   • notebook (JupyterLab)        │                           │
│  │   • python-batch (Etherscan API) │──→ S3/MinIO (raw-data)   │
│  │   • spark-batch                  │──→ Iceberg Tables         │
│  └──────────────────────────────────┘                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │   python_streaming_apps_layer.yml                    │       │
│  │   • python-job-mined-blocks-watcher                  │──→ Kafka Topics  │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │   spark_streaming_apps_layer.yml                     │       │
│  │   • spark-app-apk-comsumption  ──→ Redis             │       │
│  │   • spark-app-multiplex-bronze ──→ bronze.kafka_*    │       │
│  │   • spark-app-silver-*         ──→ silver.*          │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │   orchestration_layer.yml                            │       │
│  │   • airflow_pg (PostgreSQL)                          │       │
│  │   • airflow-apiserver (:8080)                        │       │
│  │   • airflow-scheduler                                │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Equivalências Cloud

| Componente On-premises         | Equivalente Cloud (AWS + Databricks)              |
|-------------------------------|---------------------------------------------------|
| Docker Compose network `vpc_dm`| VPC com Security Groups na AWS                   |
| Arquivos `.conf` locais        | AWS Secrets Manager / Parameter Store            |
| JupyterLab (notebook)          | Databricks Notebooks                             |
| Airflow (LocalExecutor)        | Databricks Workflows                             |
| PostgreSQL (metastore Airflow) | Aurora PostgreSQL Serverless                     |
| MinIO (S3 local)               | Amazon S3                                         |
| Kafka (Confluent local)        | Amazon MSK (Managed Streaming for Apache Kafka)  |
| Redis local                    | Amazon ElastiCache for Redis / Azure CosmosDB    |
