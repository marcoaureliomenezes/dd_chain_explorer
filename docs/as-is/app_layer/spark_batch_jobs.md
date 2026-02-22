# Jobs Spark Batch — Processamento e Manutenção do Data Lake

## 1. Objetivo

Os Jobs Spark Batch são responsáveis por:
1. **Criação e gerenciamento da estrutura DDL** das tabelas Iceberg no Data Lake (Bronze, Silver, Gold)
2. **Processamento periódico** de dados para cálculo de contratos populares e ingestão batch
3. **Manutenção das tabelas Iceberg** criadas por jobs Streaming (compactação, expiração de snapshots)

Todos os jobs são orquestrados pelo Apache Airflow e executados via `DockerOperator`.

---

## 2. Localização do Código

```
docker/app_layer/spark-batch-jobs/
├── Dockerfile
├── requirements.txt
├── conf/
│   └── spark-defaults.conf           # Configuração Spark (Iceberg, MinIO, Nessie)
└── src/
    ├── entrypoint.sh                 # Script de submit Spark
    ├── ddl_iceberg_tables/           # DDL — criação/deleção de tabelas
    │   ├── job_1_create_bronze_tables.py
    │   ├── job_2_create_silvers_s_apps.py
    │   ├── job_3_create_silver_table_logs.py
    │   ├── job_4_create_gold_views.py
    │   ├── job_5_delete_all_tables.py
    │   └── table_creator.py          # Utilitário para criação de tabelas
    ├── maintenance_streaming_tables/ # Manutenção de tabelas Iceberg
    │   ├── 1_rewrite_data_files.py
    │   ├── 2_rewrite_and_expire_manifests.py
    │   ├── 3_monitore_streaming.py
    │   └── iceberg_maintenance.py    # Utilitário de manutenção
    ├── periodic_spark_processing/    # Jobs de processamento periódico
    │   ├── 1_get_popular_contracts.py
    │   └── 2_ingest_txs_data_to_bronze.py
    └── utils/
        ├── iceberg_utils.py          # Utilitários Iceberg
        └── spark_utils.py            # Utilitário SparkSession
```

---

## 3. Estrutura das Tabelas do Data Lake

### 3.1 Camada Bronze

Criada por `job_1_create_bronze_tables.py`:

| Tabela                              | Namespace | Descrição                                              |
|-------------------------------------|-----------|--------------------------------------------------------|
| `b_fast.kafka_topics_multiplexed`   | Nessie    | Landing zone — dados raw de todos os tópicos Kafka    |
| `bronze.popular_contracts_txs`      | Nessie    | Transações de contratos populares (captura batch)      |

### 3.2 Camada Silver

Criada por `job_2_create_silvers_s_apps.py` e `job_3_create_silver_table_logs.py`:

| Tabela                              | Namespace | Descrição                                        |
|-------------------------------------|-----------|--------------------------------------------------|
| `s_apps.mined_blocks_events`        | Nessie    | Eventos de blocos minerados (bloco, hash, ts)   |
| `s_apps.blocks_fast`                | Nessie    | Dados completos dos blocos                       |
| `s_apps.blocks_txs_fast`            | Nessie    | Relação bloco ↔ hash de transações              |
| `s_apps.transactions_fast`          | Nessie    | Dados completos de transações                    |
| `s_logs.apps_logs_fast`             | Nessie    | Logs estruturados de aplicações                 |

### 3.3 Camada Gold (Views)

Criada por `job_4_create_gold_views.py`:

Views SQL sobre as tabelas Silver para facilitar consultas analíticas via Dremio.

---

## 4. Jobs de DDL (`ddl_iceberg_tables`)

### 4.1 `job_1_create_bronze_tables.py`

Cria as tabelas Bronze no namespace Nessie. Exemplo de criação:

```python
spark.sql("""
    CREATE TABLE IF NOT EXISTS b_fast.kafka_topics_multiplexed (
        key BINARY,
        value BINARY,
        partition INT,
        offset LONG,
        ingestion_time TIMESTAMP,
        topic STRING,
        dat_ref STRING
    )
    USING iceberg
    PARTITIONED BY (dat_ref)
""")
```

### 4.2 `job_2_create_silvers_s_apps.py`

Cria as tabelas Silver para dados de blocos e transações (namespace `s_apps`).

### 4.3 `job_3_create_silver_table_logs.py`

Cria a tabela Silver para logs de aplicação (namespace `s_logs`).

### 4.4 `job_4_create_gold_views.py`

Cria views sobre as tabelas Silver para a camada Gold.

### 4.5 `job_5_delete_all_tables.py`

Deleta todas as tabelas do Data Lake (usado pela DAG `pipeline_eventual_2_delete_environment.py`).

---

## 5. Jobs de Processamento Periódico (`periodic_spark_processing`)

### 5.1 `1_get_popular_contracts.py`

**Função:** Identifica os contratos mais transacionados e salva no Redis DB 3 para uso pelos Jobs Python Batch.

**Lógica:**
```python
# Lê tabela Silver de transações
df = spark.read.table(TABLE_NAME)  # silver.transactions_fast

# Agrupa por endereço de contrato e conta transações
popular_contracts = (
    df.groupBy("to")
      .count()
      .orderBy("count", ascending=False)
      .filter(col("to") != "")
      .limit(100)
)

# Salva no Redis DB 3
for row in popular_contracts.collect():
    redis_client.set(row["to"], row["count"])
```

**Variáveis de ambiente:**
```bash
TABLE_NAME=silver.transactions_fast
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASS=secret
REDIS_DB=3
```

### 5.2 `2_ingest_txs_data_to_bronze.py`

**Função:** Lê arquivos JSON de transações do S3 (staging area) e os ingesta na tabela `bronze.popular_contracts_txs`.

**Lógica:**
```python
# Lê arquivos JSON do S3 (particionados por data/hora)
df = spark.read.json(f"s3a://raw-data/contracts_transactions/year=.../month=.../day=.../hour=...")

# Escreve na tabela Bronze Iceberg
df.writeTo(TABLE_NAME).append()
```

**Variáveis de ambiente:**
```bash
TABLE_NAME=bronze.popular_contracts_txs
EXEC_DATE={{ execution_date }}    # Fornecido pelo Airflow
S3_URL=http://minio:9000
```

---

## 6. Jobs de Manutenção (`maintenance_streaming_tables`)

As tabelas Iceberg criadas por jobs Streaming acumulam pequenos arquivos Parquet devido ao append contínuo. Jobs de manutenção são executados periodicamente para otimização.

### 6.1 `1_rewrite_data_files.py`

**Função:** Compacta pequenos arquivos Parquet em arquivos maiores.

```python
spark.sql(f"CALL nessie.system.rewrite_data_files(table => '{TABLE_FULLNAME}')")
```

Executado a cada **12 horas** para todas as tabelas Silver e Bronze.

### 6.2 `2_rewrite_and_expire_manifests.py`

**Função:** Reescreve manifestos e expira snapshots antigos (reduz metadados).

```python
spark.sql(f"""
    CALL nessie.system.expire_snapshots(
        table => '{TABLE_FULLNAME}',
        older_than => TIMESTAMP '{cutoff_timestamp}',
        retain_last => {MIN_SNAPSHOTS}
    )
""")
```

Executado a cada **24 horas** (via `BranchPythonOperator` no Airflow).

**Variáveis de ambiente:**
```bash
TABLE_FULLNAME=b_fast.kafka_topics_multiplexed
HOURS_RETAIN=24
MIN_SNAPSHOTS=5
```

### 6.3 `3_monitore_streaming.py`

**Função:** Verifica se os jobs Streaming estão ativos consultando o timestamp da última mensagem nas tabelas Silver.

```python
# Lê o registro mais recente da tabela
latest = spark.sql(f"""
    SELECT max(ingestion_time) as latest_ts
    FROM {TABLE_NAME}
""").collect()[0]["latest_ts"]

# Calcula lag
lag_seconds = (datetime.now() - latest).seconds
redis_client.set("streaming_lag", lag_seconds)
```

Executado a cada **15 minutos** pela DAG de monitoramento. O resultado é usado pelo `SparkStreamingJobsHandler` para reiniciar jobs com lag excessivo.

---

## 7. Tabelas Gerenciadas — Manutenção Periódica

| Tabela                              | Compactação (12h) | Expiração (24h) | Monitoramento |
|-------------------------------------|--------------------|-----------------|---------------|
| `b_fast.kafka_topics_multiplexed`   | ✅                | ✅              | —             |
| `s_apps.mined_blocks_events`        | ✅                | ✅              | —             |
| `s_apps.blocks_fast`                | ✅                | ✅              | —             |
| `s_apps.blocks_txs_fast`            | ✅                | ✅              | —             |
| `s_apps.transactions_fast`          | ✅                | ✅              | ✅            |
| `s_logs.apps_logs_fast`             | ✅                | ✅              | —             |

---

## 8. Configuração Spark (`spark-defaults.conf`)

```properties
# Catálogo Nessie como catálogo Iceberg
spark.sql.catalog.nessie=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.nessie.catalog-impl=org.apache.iceberg.nessie.NessieCatalog
spark.sql.catalog.nessie.uri=${NESSIE_URI}
spark.sql.catalog.nessie.ref=main
spark.sql.catalog.nessie.authentication.type=NONE
spark.sql.catalog.nessie.warehouse=s3a://warehouse/

# MinIO como Object Storage S3-compatible
spark.hadoop.fs.s3a.endpoint=${S3_URL}
spark.hadoop.fs.s3a.access.key=${AWS_ACCESS_KEY_ID}
spark.hadoop.fs.s3a.secret.key=${AWS_SECRET_ACCESS_KEY}
spark.hadoop.fs.s3a.path.style.access=true
```

---

## 9. Adaptações Necessárias para a Cloud

| Item                        | On-premises                              | Cloud (Databricks)                     | Adaptação                                              |
|-----------------------------|------------------------------------------|----------------------------------------|--------------------------------------------------------|
| Catálogo Iceberg (Nessie)   | NessieCatalog + MinIO                    | Unity Catalog nativo                   | Remover config Nessie; usar `catalog.unitycatalog`     |
| Spark DDL                   | `CREATE TABLE ... USING iceberg`         | `CREATE TABLE ... USING DELTA` ou Iceberg no UC | Adaptar DDL para Delta Lake ou Iceberg no UC  |
| `system.rewrite_data_files` | Procedimento Nessie/Iceberg             | `OPTIMIZE` no Delta Lake               | Substituir `CALL` por `OPTIMIZE` SQL                   |
| `expire_snapshots`          | Procedimento Iceberg                    | `VACUUM` no Delta Lake                 | Substituir por `VACUUM` statement                      |
| S3 (MinIO)                  | `s3a://` com endpoint customizado       | `s3://` nativo AWS                     | Remover `endpoint` e `path.style.access`               |
| Airflow DockerOperator      | Container com spark-submit               | Databricks Job runs via Workflows       | Criar Databricks Jobs para cada script PySpark         |
