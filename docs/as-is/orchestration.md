# Orquestração — Apache Airflow

## 1. Visão Geral

O Apache Airflow é o **orquestrador central** do projeto, responsável por:
- Provisionar e destruir o ambiente do Data Lake (Kafka, tabelas Iceberg)
- Executar jobs periódicos de captura batch de dados
- Gerenciar a manutenção das tabelas Iceberg (compactação, expiração de snapshots)
- Monitorar a saúde dos jobs Spark Streaming e reiniciá-los quando necessário
- Gerenciar o ciclo de vida dos jobs Spark Streaming

Todos os jobs são executados via **DockerOperator** ou **DockerSwarmOperator**, que disparam containers a partir das imagens publicadas no Docker Hub.

---

## 2. Configuração do Airflow

### Executor e Backend:

```yaml
AIRFLOW__CORE__EXECUTOR: LocalExecutor         # Jobs executados localmente no Scheduler
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow_pg/airflow
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
```

### Acesso ao Docker:

O Airflow monta o socket Docker para executar containers:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

Isso permite ao Scheduler disparar containers Docker (DockerOperator) e serviços Swarm (DockerSwarmOperator) diretamente.

### Localização das DAGs:

```
mnt/airflow/dags/
├── dag_eventual_1_create_environment.py
├── dag_eventual_2_delete_environment.py
├── dag_hourly_2_contracts_transactions.py
├── dag_periodic_maintenance_streaming_tables.py
├── dag_periodic_monitoring_streaming_tables.py
├── dag_streaming_1_spark_jobs.py
└── python_scripts/
    ├── restart_spark_streaming_drivers.py
    └── validate_cache_popular_contracts.py
```

---

## 3. DAGs Implementadas

### 3.1 `pipeline_eventual_1_create_environment.py` — Criação do Ambiente

**Agendamento:** `@once` (execução única sob demanda)  
**Propósito:** Provisionamento inicial do ambiente: cria tópicos Kafka e todas as tabelas Iceberg do Data Lake.

#### Diagrama de Fluxo:

```
STARTING_TASK
    ├── CREATE_KAFKA_TOPICS
    │   └── Cria tópicos via onchain-batch-txs:1.0.0
    │       (topics_dev.ini)
    │
    └── CREATE_BRONZE_TABLES ──→ CREATE_SILVER_BLOCKS_FAST ──→ CREATE_SILVER_LOGS_FAST ──→ CREATE_GOLD_VIEWS ──→ FINAL_TASK
        (spark-batch-jobs:1.0.0)    (spark-batch-jobs:1.0.0)    (spark-batch-jobs:1.0.0)    (spark-batch-jobs:1.0.0)
```

#### Tasks:

| Task                       | Imagem Docker                         | Script                                | Função                                    |
|----------------------------|---------------------------------------|---------------------------------------|-------------------------------------------|
| `STARTING_TASK`            | —                                     | `sleep 2`                             | Task de início                            |
| `CREATE_KAFKA_TOPICS`      | `onchain-batch-txs:1.0.0`             | `kafka_maintenance/0_create_topics.py`| Cria tópicos Kafka                        |
| `CREATE_BRONZE_TABLES`     | `spark-batch-jobs:1.0.0`              | `ddl_iceberg_tables/job_1_create_bronze_tables.py` | Cria tabela Bronze       |
| `CREATE_SILVER_BLOCKS_FAST`| `spark-batch-jobs:1.0.0`              | `ddl_iceberg_tables/job_2_create_silvers_s_apps.py`| Cria tabelas Silver      |
| `CREATE_SILVER_LOGS_FAST`  | `spark-batch-jobs:1.0.0`              | `ddl_iceberg_tables/job_3_create_silver_table_logs.py`| Cria tabela de logs    |
| `CREATE_GOLD_VIEWS`        | `spark-batch-jobs:1.0.0`              | `ddl_iceberg_tables/job_4_create_gold_views.py`    | Cria views Gold          |
| `FINAL_TASK`               | —                                     | `sleep 2`                             | Task final                                |

---

### 3.2 `pipeline_eventual_2_delete_environment` — Destruição do Ambiente

**Agendamento:** `@once` (execução única sob demanda)  
**Propósito:** Destrói o ambiente: deleta tópicos Kafka e todas as tabelas Iceberg.

#### Tasks:

| Task                    | Imagem Docker                  | Script                                         | Função                        |
|-------------------------|--------------------------------|------------------------------------------------|-------------------------------|
| `starting_task`         | —                              | `sleep 2`                                      | Task de início                |
| `delete_kafka_topics`   | `onchain-batch-txs:1.0.0`      | `kafka_maintenance/1_delete_topics.py`         | Deleta tópicos Kafka          |
| `delete_all_tables`     | `spark-batch-jobs:1.0.0`       | `ddl_iceberg_tables/job_5_delete_all_tables.py`| Deleta todas as tabelas Iceberg |

---

### 3.3 `pipeline_hourly_2_contracts_transactions` — Captura Horária de Transações

**Agendamento:** `@hourly` (toda hora, com catchup habilitado)  
**Propósito:** Pipeline principal de captura batch. A cada hora, identifica contratos populares e captura suas transações via Etherscan API.

#### Diagrama de Fluxo:

```
STARTING_TASK
    │
    ▼
VALIDATE_CACHE
    │ (BranchPythonOperator)
    ├── cache válido ──→ BY_PASS_CACHE_FULLFILMENT ──┐
    │                                                │
    └── cache inválido                               │
        ▼                                            │
GET_POPULAR_CONTRACTS_AND_CACHE_THEM ───────────────┘
(spark-batch-jobs: 1_get_popular_contracts.py)
    │
    ▼
CAPTURE_AND_STAGE_TXS_BY_CONTRACT
(onchain-batch-txs: 1_capture_and_ingest_contracts_txs.py)
    │
    ▼
INGEST_TX_DATA_TO_BRONZE
(spark-batch-jobs: 2_ingest_txs_data_to_bronze.py)
```

#### Tasks:

| Task                                    | Imagem Docker                   | Função                                                         |
|-----------------------------------------|---------------------------------|----------------------------------------------------------------|
| `STARTING_TASK`                         | —                               | Início da execução                                             |
| `VALIDATE_CACHE`                        | Python (BranchPythonOperator)   | Verifica se Redis DB 3 possui contratos em cache               |
| `GET_POPULAR_CONTRACTS_AND_CACHE_THEM`  | `spark-batch-jobs:1.0.0`        | Calcula contratos populares e cacheia no Redis DB 3            |
| `BY_PASS_CACHE_FULLFILMENT`             | —                               | Bypass quando cache já está populado                           |
| `CAPTURE_AND_STAGE_TXS_BY_CONTRACT`     | `onchain-batch-txs:1.0.0`       | Captura txs via Etherscan API → S3 (JSON staging)              |
| `INGEST_TX_DATA_TO_BRONZE`              | `spark-batch-jobs:1.0.0`        | Lê JSONs do S3 e ingesta em `bronze.popular_contracts_txs`     |

**Variável Airflow (Jinja templating):**
```python
"EXEC_DATE": "{{ execution_date }}"
```
O Airflow injeta a data de execução, permitindo que o job de captura saiba qual janela de 1 hora buscar.

---

### 3.4 `pipeline_periodic_maintenance_streaming_tables.py` — Manutenção das Tabelas

**Agendamento:** `0 */12 * * *` (a cada 12 horas)  
**Propósito:** Mantém a saúde das tabelas Iceberg criadas pelos jobs Streaming, executando compactação e expiração de snapshots.

#### Padrão por tabela (BranchPythonOperator):

```
STARTING_TASK
    │
    ▼
REWRITE_FILES_{TABLE}   (toda execução — a cada 12h)
    │
    ▼
BRANCH_OPER_{TABLE}     (BranchPythonOperator — corre a cada 24h)
    ├── hora % 24 == 0 → REWRITE_EXPIRE_MANIFESTS_{TABLE}
    └── hora % 24 != 0 → DUMMY_OPER_{TABLE}
```

#### Tabelas mantidas:

| Tabela Iceberg                        | Compactação (12h)         | Expiração Snapshots (24h)         |
|---------------------------------------|---------------------------|-----------------------------------|
| `b_fast.kafka_topics_multiplexed`     | REWRITE_FILES_BRONZE_FAST | REWRITE_EXPIRE_MANIFESTS_BRONZE_FAST |
| `s_apps.mined_blocks_events`          | REWRITE_FILES_BLOCKS_EVENTS | REWRITE_EXPIRE_MANIFESTS_BLOCKS_EVENTS |
| `s_apps.blocks_fast`                  | REWRITE_FILES_BLOCKS_FAST | REWRITE_EXPIRE_MANIFESTS_BLOCKS_FAST |
| `s_apps.blocks_txs_fast`              | REWRITE_FILES_BLOCKS_TXS_FAST | REWRITE_EXPIRE_MANIFESTS_BLOCKS_TXS_FAST |
| `s_apps.transactions_fast`            | REWRITE_FILES_TXS_FAST    | REWRITE_EXPIRE_MANIFESTS_TXS_FAST |
| `s_logs.apps_logs_fast`               | REWRITE_FILES_LOGS_FAST   | REWRITE_EXPIRE_MANIFESTS_LOGS_FAST |

---

### 3.5 `pipeline_periodic_monitoring_streaming_tables.py` — Monitoramento de Streaming

**Agendamento:** `*/15 * * * *` (a cada 15 minutos)  
**Propósito:** Monitora a saúde dos jobs Spark Streaming verificando o lag (tempo desde o último registro nas tabelas Silver). Se o lag for excessivo, reinicia os jobs automaticamente.

#### Diagrama de Fluxo:

```
STARTING_TASK
    │
    ▼
SEE_LATEST_MESSAGES_STREAMING_TABLES
(spark-batch-jobs: 3_monitore_streaming.py)
→ Consulta max(ingestion_time) das tabelas
→ Calcula lag e salva no Redis
    │
    ▼
TAKING_ACTION_STREAMING_TABLES
(PythonOperator: SparkStreamingJobsHandler.run)
→ Se lag > threshold: reinicia containers Spark Streaming
```

#### `SparkStreamingJobsHandler`:

```python
# python_scripts/restart_spark_streaming_drivers.py
class SparkStreamingJobsHandler:
    def run(self):
        # Lê o lag do Redis
        # Se lag > threshold, reinicia os containers via Docker API
        # docker restart spark-app-multiplex-bronze
        # docker restart spark-app-silver-*
```

---

### 3.6 `pipeline_streaming_1_spark_jobs` — Gerenciamento de Streaming

**Agendamento:** `@once` (execução única sob demanda)  
**Propósito:** Inicia os jobs Spark Streaming como containers `DockerOperator` ou `DockerSwarmOperator`.

#### Diagrama de Fluxo:

```
starting_task
    ├── spark_app_multiplex_bronze (DockerOperator)
    ├── spark_app_silver_blocks    (DockerOperator)
    └── test_docker_operator       (DockerSwarmOperator — experimental)
```

> Esta DAG é experimental e demonstra o uso do `DockerSwarmOperator` para gerenciar jobs como serviços Swarm.

---

## 4. Visão Geral das DAGs — Tabela Resumo

| DAG                                             | Trigger          | Propósito                                  | Operador Principal     |
|-------------------------------------------------|------------------|---------------------------------------------|------------------------|
| `pipeline_eventual_1_create_environment`        | `@once`          | Criar ambiente (Kafka + tabelas Iceberg)     | DockerOperator         |
| `pipeline_eventual_2_delete_environment`        | `@once`          | Destruir ambiente                            | DockerOperator         |
| `pipeline_hourly_2_contracts_transactions`      | `@hourly`        | Captura batch transações de contratos        | DockerOperator         |
| `pipeline_periodic_maintenance_streaming_tables`| `0 */12 * * *`   | Manutenção tabelas Iceberg Streaming (12h)  | DockerOperator         |
| `pipeline_periodic_monitoring_streaming_tables` | `*/15 * * * *`   | Monitoramento e restart de jobs Streaming   | DockerOperator + Python|
| `pipeline_streaming_1_spark_jobs`               | `@once`          | Inicialização de jobs Spark Streaming        | DockerSwarmOperator    |

---

## 5. Diagrama Completo de Agendamentos

```
                    LINHA DO TEMPO — EXECUÇÕES AIRFLOW
                    
T+0 (1x)      │  pipeline_eventual_1_create_environment
               │  └── Cria Kafka topics + tabelas Iceberg
               │
T+0 (contínuo)│  pipeline_streaming_1_spark_jobs
               │  └── Inicia jobs Spark Streaming
               │
A cada hora ──┤  pipeline_hourly_2_contracts_transactions
               │  └── Captura txs de contratos populares
               │
A cada 15 min ┤  pipeline_periodic_monitoring_streaming_tables
               │  └── Verifica lag e reinicia streaming se necessário
               │
A cada 12h ───┤  pipeline_periodic_maintenance_streaming_tables
               │  └── Compacta arquivos Iceberg
               │  └── Expira snapshots (1x por dia)
               │
T+N (1x)      │  pipeline_eventual_2_delete_environment
               └── Destrói ambiente completo
```

---

## 6. Operadores Docker Utilizados

### DockerOperator

Executa um container Docker no mesmo host onde o Scheduler está rodando.

```python
DockerOperator(
    image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
    network_mode="vpc_dm",
    docker_url="unix:/var/run/docker.sock",
    auto_remove="force",
    mount_tmp_dir=False,
    tty=False,
    entrypoint="sh /app/entrypoint.sh /app/periodic_spark_processing/1_get_popular_contracts.py",
    environment={ "SPARK_MASTER": ..., "S3_URL": ..., ... }
)
```

### DockerSwarmOperator

Cria um serviço Swarm (one-shot task), útil para jobs que precisam rodar em nós específicos do cluster.

```python
DockerSwarmOperator(
    image="marcoaureliomenezes/spark-streaming-jobs:1.0.0",
    api_version='auto',
    networks=["vpc_dm"],
    docker_url="unix:/var/run/docker.sock",
    tty=False,
    enable_logging=True,
    auto_remove="force",
    force_pull=True,
    command="sh /app/entrypoint.sh /app/pyspark/4_job_silver_transactions.py",
    environment={ ... }
)
```

---

## 7. Adaptações Necessárias para a Cloud

| Item                              | On-premises                              | Cloud (Databricks + AWS)                   | Adaptação                                              |
|-----------------------------------|------------------------------------------|--------------------------------------------|--------------------------------------------------------|
| Apache Airflow                    | Docker Compose / Swarm (LocalExecutor)   | Databricks Workflows / AWS MWAA            | Recriar DAGs como Databricks Jobs ou Pipelines         |
| DockerOperator                    | Dispara containers locais                | Databricks Jobs com clusters dedicados     | Substituir por chamadas à API REST do Databricks       |
| DockerSwarmOperator               | Cria serviços Swarm                      | ECS Task execution / Databricks Jobs       | Substituir por AWS ECS Task ou Databricks Jobs         |
| PostgreSQL (metastore Airflow)    | PostgreSQL 16 local                      | Amazon Aurora PostgreSQL Serverless        | Apontamento de conexão                                 |
| Jinja `{{ execution_date }}`      | Nativo do Airflow                        | Nativo do Airflow (MWAA) / Parâmetros DW  | Sem alteração (MWAA) ou reconfiguração (Databricks)    |
| DAG de manutenção Iceberg         | `CALL system.rewrite_data_files()`       | `OPTIMIZE` (Delta Lake) no DW             | Substituir por comandos Delta Lake SQL                  |
| Monitoramento de Streaming        | `SparkStreamingJobsHandler` + Docker API | Databricks Workflows com alertas          | Usar DLT observability ou Databricks alertas           |
