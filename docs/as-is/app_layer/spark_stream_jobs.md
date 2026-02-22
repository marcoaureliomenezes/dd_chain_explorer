# Jobs Spark Streaming — Processamento em Tempo Real

## 1. Objetivo

Os Jobs Spark Streaming são responsáveis pelo **processamento contínuo dos dados capturados** pelos Jobs Python Streaming. Eles consomem os dados do Kafka e os persistem nas camadas **Bronze** e **Silver** do Data Lake em formato Apache Iceberg.

Com exceção do job de monitoramento de API Keys (que escreve no Redis), todos os demais jobs escrevem em tabelas Iceberg gerenciadas pelo catálogo Nessie no MinIO.

---

## 2. Localização do Código

```
docker/app_layer/spark-streaming-jobs/
├── Dockerfile
├── requirements.txt
└── src/
    ├── entrypoint.sh                                # Script de entrada (submit Spark)
    ├── i_dm_streaming.py                            # Interface abstrata IDmStreaming
    ├── pyspark/
    │   ├── 1_api_key_monitor.py                     # Kafka → Redis (consumo de API Keys)
    │   ├── 2_job_bronze_multiplex.py                # Kafka múltiplos tópicos → Bronze Iceberg
    │   ├── 3_job_silver_apps_logs.py                # Bronze → Silver (logs de app)
    │   ├── 4_job_silver_blocks_events.py            # Bronze → Silver (eventos de blocos)
    │   ├── 5_job_silver_blocks.py                   # Bronze → Silver (dados de blocos)
    │   └── 6_job_silver_transactions.py             # Bronze → Silver (transações)
    └── utils/
        ├── dm_schemas.py                            # Schemas PySpark das tabelas
        └── spark_utils.py                           # Utilitário SparkSession
```

---

## 3. Interface Base `IDmStreaming`

Todos os jobs Spark Streaming implementam a interface `IDmStreaming`, que define o padrão:

```python
class IDmStreaming(ABC):

    @abstractmethod
    def config_source(self, src_properties: Dict) -> Self:
        """Configura a fonte de dados (Kafka options)"""

    @abstractmethod
    def config_sink(self, tables_output: Dict, sink_properties: Dict) -> Self:
        """Configura o destino (tabelas Iceberg, Redis, checkpoint)"""

    @abstractmethod
    def extract(self) -> Self:
        """Lê dados do Kafka via readStream"""

    @abstractmethod
    def transform(self) -> Self:
        """Aplica transformações no DataFrame streaming"""

    @abstractmethod
    def load(self) -> None:
        """Escreve os dados no destino via writeStream"""
```

Esse padrão garante uniformidade e facilita testes, manutenção e migração para outras plataformas (ex: Databricks DLT).

---

## 4. Arquitetura das Camadas Bronze e Silver

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                   PIPELINE SPARK STREAMING — CAMADAS BRONZE/SILVER             │
│                                                                                │
│  KAFKA TOPICS                                                                  │
│  ├── mainnet.0.application.logs   ──────────────────────────┐                 │
│  ├── mainnet.0.batch.logs          ──────────────────────────┤                 │
│  ├── mainnet.1.mined_blocks.events ──────────────────────────┤                 │
│  ├── mainnet.2.blocks.data         ──────────────────────────┤                 │
│  └── mainnet.4.transactions.data  ──────────────────────────┘                 │
│                                             │                                  │
│                                             ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐      │
│  │  Job 2: 2_job_bronze_multiplex.py                                    │      │
│  │  • Consome TODOS os 5 tópicos simultaneamente                        │      │
│  │  • Preserva key, value (raw), partition, offset, timestamp, topic    │      │
│  │  • Adiciona coluna dat_ref (particionamento por data)                │      │
│  │  • Escreve em: bronze.kafka_topics_multiplexed (Iceberg)             │      │
│  │  • Trigger: a cada 1 minuto                                          │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
│                                             │                                  │
│                            ┌────────────────┴──────────────────────────┐       │
│                            ▼                                           ▼       │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐    │
│  │  Job 3: Silver Logs             │   │  Job 4: Silver Blocks Events    │    │
│  │  • Filtra topic logs            │   │  • Filtra topic blocks events   │    │
│  │  • Deserializa Avro             │   │  • Deserializa Avro             │    │
│  │  → s_logs.apps_logs_fast        │   │  → s_apps.mined_blocks_events   │    │
│  └─────────────────────────────────┘   └─────────────────────────────────┘    │
│                            ▼                                           ▼       │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐    │
│  │  Job 5: Silver Blocks           │   │  Job 6: Silver Transactions     │    │
│  │  • Filtra topic blocks data     │   │  • Filtra topic transactions    │    │
│  │  • Deserializa Avro             │   │  • Deserializa Avro             │    │
│  │  → s_apps.blocks_fast           │   │  → s_apps.transactions_fast     │    │
│  │  → s_apps.blocks_txs_fast       │   │                                 │    │
│  └─────────────────────────────────┘   └─────────────────────────────────┘    │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐      │
│  │  Job 1: 1_api_key_monitor.py (ESPECIAL)                             │      │
│  │  • Consome: mainnet.0.application.logs                               │      │
│  │  • Filtra mensagens "API_request;{api_key}"                          │      │
│  │  • Janela de agregação: 1 dia                                        │      │
│  │  • Contagem de requisições por chave                                 │      │
│  │  → REDIS DB 2: {api_key: {num_req_1d, start, end, last_req}}        │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Detalhamento dos Jobs

### 5.1 Job 2: `2_job_bronze_multiplex.py` — KafkaIngestorMultiplexed

**Função:** Ingesta múltiplos tópicos Kafka em uma única tabela Bronze, preservando o payload raw.

**Transformação:**
```python
df_streaming = (
    df_streaming
    .withColumn("dat_ref", date_format(col("timestamp"), "yyyy-MM-dd"))
    .withColumn("ingestion_time", col("timestamp").cast("timestamp"))
    .select("key", "value", "partition", "offset", "ingestion_time", "topic", "dat_ref")
)
```

**Schema da tabela `bronze.kafka_topics_multiplexed`:**

| Coluna           | Tipo      | Descrição                                    |
|------------------|-----------|----------------------------------------------|
| `key`            | BINARY    | Chave da mensagem Kafka                      |
| `value`          | BINARY    | Payload raw (Avro serializado)               |
| `partition`      | INTEGER   | Partição Kafka                               |
| `offset`         | LONG      | Offset da mensagem                           |
| `ingestion_time` | TIMESTAMP | Timestamp de ingestão no Kafka               |
| `topic`          | STRING    | Nome do tópico Kafka de origem               |
| `dat_ref`        | STRING    | Data de referência `yyyy-MM-dd` (partição)   |

> Esta tabela é a **landing zone** do Data Lake. Todos os jobs Silver leem dela.

**Configuração (Swarm):**
```yaml
CHECKPOINT_PATH: "s3a://spark/checkpoints/iceberg/kafka_topics_multiplexed"
TOPICS: "mainnet.0.application.logs,mainnet.0.batch.logs,mainnet.1.mined_blocks.events,mainnet.2.blocks.data,mainnet.4.transactions.data"
CONSUMER_GROUP: "cg_bronze"
STARTING_OFFSETS: "earliest"
MAX_OFFSETS_PER_TRIGGER: 30000
TABLE_BRONZE: "b_fast.kafka_topics_multiplexed"
TRIGGER_TIME: "1 minute"
```

---

### 5.2 Job 3: `3_job_silver_apps_logs.py` — Silver Logs

**Função:** Deserializa e filtra logs de aplicação do Bronze para a camada Silver.

**Lógica:**
1. Lê da tabela Bronze filtrando `topic = TOPIC_LOGS`
2. Desserializa o campo `value` (Avro) via `from_avro()`
3. Extrai campos estruturados do log
4. Escreve em `s_logs.apps_logs_fast`

---

### 5.3 Job 4: `4_job_silver_blocks_events.py` — Silver Blocks Events

**Função:** Processa eventos de blocos minerados do Bronze para Silver.

**Lógica:**
1. Lê da tabela Bronze filtrando `topic = TOPIC_BLOCKS_EVENTS`
2. Desserializa Avro → extrai `block_timestamp`, `block_number`, `block_hash`
3. Escreve em `s_apps.mined_blocks_events`

---

### 5.4 Job 5: `5_job_silver_blocks.py` — Silver Blocks

**Função:** Processa dados completos de blocos e a relação bloco-transações.

**Lógica:**
1. Lê da tabela Bronze filtrando `topic = TOPIC_BLOCKS`
2. Desserializa Avro → extrai todos os campos do bloco
3. Escreve dados do bloco em `s_apps.blocks_fast`
4. Escreve relação bloco→transações em `s_apps.blocks_txs_fast`

---

### 5.5 Job 6: `6_job_silver_transactions.py` — Silver Transactions

**Função:** Processa dados completos de transações do Bronze para Silver.

**Lógica:**
1. Lê da tabela Bronze filtrando `topic = TOPIC_TXS`
2. Desserializa Avro → extrai todos os campos da transação
3. Escreve em `s_apps.transactions_fast`

---

### 5.6 Job 1: `1_api_key_monitor.py` — API Key Monitor (ESPECIAL)

**Função:** Único job com destino Redis (não Iceberg). Monitora o consumo das API Keys.

**Lógica detalhada:**
```python
def transform(self):
    df = (df_streaming
        .withColumn("data", from_avro(expr("substring(value, 6)"), topic_schema))
        .select("kafka_timestamp", "data.*")
        .filter(col("message").startswith("API_request"))
        .withColumn("api_key", split(col("message"), ";").getItem(1))
    )
    # Janela de 1 dia com watermark de 1 dia
    window_1D = window(col("kafka_timestamp"), "1 day")
    df = (df
        .withWatermark("kafka_timestamp", "1 day")
        .groupBy(col("api_key"), window_1D)
        .agg(count("*").alias("count"), max("kafka_timestamp").alias("max_timestamp"))
    )
```

**Escrita no Redis (foreachBatch):**
```python
def __batch_to_redis(self, batch_df, batch_id):
    for row in batch_df.collect():
        redis_client.hset(row['name'], mapping={
            "start": row['start'],
            "end": row['end'],
            "num_req_1d": row['num_req_1d'],
            "last_req": row['last_req']
        })
```

---

## 6. Tabelas do Data Lake — Camadas Bronze e Silver

### Camada Bronze

| Tabela                                  | Catalogo | Schema | Job que escreve            |
|-----------------------------------------|----------|--------|---------------------------|
| `b_fast.kafka_topics_multiplexed`       | Nessie   | Iceberg| Job 2 (multiplex-bronze)  |
| `bronze.popular_contracts_txs`          | Nessie   | Iceberg| Spark batch (ingestão)    |

### Camada Silver

| Tabela                           | Catalogo | Schema | Job que escreve              |
|----------------------------------|----------|--------|------------------------------|
| `s_logs.apps_logs_fast`          | Nessie   | Iceberg| Job 3 (silver-logs)          |
| `s_apps.mined_blocks_events`     | Nessie   | Iceberg| Job 4 (silver-blocks-events) |
| `s_apps.blocks_fast`             | Nessie   | Iceberg| Job 5 (silver-blocks)        |
| `s_apps.blocks_txs_fast`         | Nessie   | Iceberg| Job 5 (silver-blocks)        |
| `s_apps.transactions_fast`       | Nessie   | Iceberg| Job 6 (silver-txs)           |

---

## 7. Entrypoint dos Jobs

O script `entrypoint.sh` padroniza o submit dos jobs Spark:

```bash
#!/bin/bash
# Recebe o script PySpark como argumento e faz o spark-submit
spark-submit \
  --master ${SPARK_MASTER_URL} \
  --executor-memory ${EXEC_MEMORY:-2g} \
  --num-executors ${NUM_EXECUTORS:-1} \
  --total-executor-cores ${TOTAL_EXEC_CORES:-2} \
  $1
```

---

## 8. Deploy

### Docker Compose (desenvolvimento):
```yaml
# spark_streaming_apps_layer.yml
spark-app-apk-comsumption:
  entrypoint: "sh /app/entrypoint.sh /app/pyspark/1_api_key_monitor.py"
  environment:
    CHECKPOINT_PATH: "s3a://spark/checkpoints/kafka-redis/api_keys_consumption_2"
    TOPIC_LOGS: "mainnet.0.application.logs"
    EXEC_MEMORY: 2g
    TOTAL_EXEC_CORES: 2
```

```bash
# docker compose -f services/compose/spark_streaming_apps_layer.yml up -d --build
```

### Docker Swarm (produção):
```bash
make deploy_prod_spark_apps
```

---

## 9. Adaptações Necessárias para a Cloud

| Item                        | On-premises                           | Cloud (Databricks)                    | Adaptação                                    |
|-----------------------------|---------------------------------------|---------------------------------------|----------------------------------------------|
| Spark Session               | Standalone cluster                    | Databricks Runtime (cluster gerenciado) | Usar `spark` já disponível no contexto DLT |
| Iceberg + Nessie            | `SparkUtils.get_spark_session()` com configs customizadas | Unity Catalog nativo    | Remover config Nessie; usar UC              |
| Schema Registry             | Confluent + `from_avro()`             | AWS Glue Schema Registry              | Adaptar `from_avro()` para Glue             |
| MinIO (S3) + checkpoints    | `s3a://spark/checkpoints/...`         | `s3://bucket/checkpoints/...`         | Atualizar `CHECKPOINT_PATH` env vars        |
| Jobs como serviços Swarm    | `spark_apps_layer.yml`                | Databricks DLT (Delta Live Tables)    | Migrar lógica de ETL para pipelines DLT     |
| Redis (API Key monitor)     | Redis local                           | Amazon ElastiCache for Redis          | Alterar `REDIS_HOST`/`REDIS_PORT`           |
