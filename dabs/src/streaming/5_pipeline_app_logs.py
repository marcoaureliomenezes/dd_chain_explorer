# Databricks notebook source
# MAGIC %md
# MAGIC # App Logs DLT Pipeline — Silver + Gold
# MAGIC
# MAGIC Pipeline dedicado ao processamento dos logs das aplicações Python on-chain.
# MAGIC Lê da tabela bronze `b_ethereum.kafka_topics_multiplexed` (produzida por `dm-ethereum`),
# MAGIC filtra o tópico `mainnet.0.application.logs`, decodifica o Avro e produz:
# MAGIC
# MAGIC ## Silver — `s_logs`
# MAGIC - `s_logs.logs_streaming`  ← logs dos jobs de streaming (MINED_BLOCKS_WATCHER, etc.)
# MAGIC - `s_logs.logs_batch`      ← logs dos jobs batch (CONTRACT_TRANSACTIONS_CRAWLER)
# MAGIC
# MAGIC ## Gold — `g_api_keys` (Materialized Views)
# MAGIC - `g_api_keys.etherscan_consumption`   ← consumo de API keys Etherscan por janela de tempo
# MAGIC - `g_api_keys.web3_keys_consumption`   ← consumo de API keys Web3 (Infura/Alchemy) por janela

# COMMAND ----------

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from pyspark.sql.avro.functions import from_avro


# ── Configuration ─────────────────────────────────────────────────────────────

CATALOG = spark.conf.get("catalog", "dd_chain_explorer_dev")

# Tópico Kafka de logs de aplicação
TOPIC_APP_LOGS = "mainnet.0.application.logs"

# APP_NAME constants — valor do campo `logger` nas mensagens de log
STREAMING_APP_NAMES = [
    "MINED_BLOCKS_EVENTS",       # 1_mined_blocks_watcher.py
    "ORPHAN_BLOCKS_CRAWLER",     # 2_orphan_blocks_watcher.py
    "BLOCK_DATA_CRAWLER",        # 3_block_data_crawler.py
    "RAW_TXS_CRAWLER",           # 4_mined_txs_crawler.py
    "TRANSACTION_INPUT_DECODER", # 5_txs_input_decoder.py
]
BATCH_APP_NAMES = [
    "CONTRACT_TRANSACTIONS_CRAWLER",  # 1_capture_and_ingest_contracts_txs.py
]

# ── Avro Schema ───────────────────────────────────────────────────────────────

AVRO_SCHEMA_APP_LOGS = """{
  "type": "record",
  "name": "Application_Logs",
  "namespace": "io.streamr.onchain",
  "fields": [
    {"name": "timestamp",     "type": "int"},
    {"name": "logger",        "type": "string"},
    {"name": "level",         "type": "string"},
    {"name": "filename",      "type": "string"},
    {"name": "function_name", "type": "string"},
    {"name": "message",       "type": "string"}
  ]
}"""


# ── Helper ────────────────────────────────────────────────────────────────────

def _parse_app_logs_from_bronze():
    """
    Lê de kafka_topics_multiplexed (bronze, pipeline dm-ethereum), filtra
    apenas o tópico de logs de aplicação e decodifica o payload Avro.

    O payload Kafka tem 5 bytes de cabeçalho do Schema Registry antes do Avro.
    """
    df = (
        spark.readStream.table(f"{CATALOG}.b_ethereum.kafka_topics_multiplexed")
        .filter(F.col("topic_name") == TOPIC_APP_LOGS)
        .withColumn("avro_payload", F.expr("substring(value, 6)"))
        .withColumn("parsed", from_avro(F.col("avro_payload"), AVRO_SCHEMA_APP_LOGS))
    )
    return df.select(
        F.col("parsed.timestamp").alias("event_ts_epoch"),
        F.to_timestamp(F.col("parsed.timestamp")).alias("event_time"),
        F.col("parsed.logger").alias("logger"),
        F.col("parsed.level").alias("level"),
        F.col("parsed.filename").alias("filename"),
        F.col("parsed.function_name").alias("function_name"),
        F.col("parsed.message").alias("message"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# ════════════════════════════════════════════════════════════════════════════
# SILVER LAYER
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 1 — Streaming App Logs → `s_logs.logs_streaming`
# MAGIC
# MAGIC Logs dos jobs de streaming: `MINED_BLOCKS_WATCHER`, `ORPHAN_BLOCKS_WATCHER`,
# MAGIC `BLOCK_DATA_CRAWLER`, `MINED_TXS_CRAWLER`, `TXS_INPUT_DECODER`.

# COMMAND ----------

@dlt.table(
    name="logs_streaming",
    comment="Silver: logs das aplicações de streaming on-chain",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_level",   "level IS NOT NULL")
@dlt.expect_or_drop("valid_message", "message IS NOT NULL")
def silver_logs_streaming():
    return (
        _parse_app_logs_from_bronze()
        .filter(F.col("logger").isin(STREAMING_APP_NAMES))
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 2 — Batch App Logs → `s_logs.logs_batch`
# MAGIC
# MAGIC Logs dos jobs batch: `CONTRACT_TRANSACTIONS_CRAWLER`.

# COMMAND ----------

@dlt.table(
    name="logs_batch",
    comment="Silver: logs das aplicações batch on-chain",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_level",   "level IS NOT NULL")
@dlt.expect_or_drop("valid_message", "message IS NOT NULL")
def silver_logs_batch():
    return (
        _parse_app_logs_from_bronze()
        .filter(F.col("logger").isin(BATCH_APP_NAMES))
    )


# ════════════════════════════════════════════════════════════════════════════
# GOLD — Materialized Views de consumo de API keys
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 1 — Etherscan API Key Consumption → `g_api_keys.etherscan_consumption`
# MAGIC
# MAGIC Agrega chamadas à API Etherscan por chave, janelas de 1h / 12h / 24h / 48h.
# MAGIC Fonte: mensagens com padrão `etherscan;api_call;api_key_name:{name};action:{act};...`

# COMMAND ----------

@dlt.table(
    name="g_api_keys.etherscan_consumption",
    comment="Gold MV: consumo de API keys Etherscan por janela de tempo (1h/12h/24h/48h)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_etherscan_consumption():
    """
    Lê dos silver logs_streaming + logs_batch, filtra mensagens de chamada
    Etherscan e agrega por api_key_name com contadores por janela de tempo.

    Padrão de log (emitido por EtherscanClient._track_call e MultiKeyEtherscanClient._track_call):
        etherscan;api_call;api_key_name:{name};action:{action};status:{status};request_count:{n}

    Uma linha por chave com contadores de requisições OK e com erro separados.
    Janelas: 1h, 2h, 12h, 24h, 48h (relativas ao kafka_timestamp da mensagem).
    """
    df = (
        dlt.read("logs_streaming")
        .unionByName(dlt.read("logs_batch"))
        .filter(F.col("message").contains("etherscan;api_call;"))
        .withColumn(
            "api_key_name",
            # [^;]+ para capturar só até o próximo ';'
            F.regexp_extract(F.col("message"), r"api_key_name:([^;]+)", 1),
        )
        .withColumn(
            "action",
            F.regexp_extract(F.col("message"), r"action:([^;]+)", 1),
        )
        .withColumn(
            "call_status",
            F.regexp_extract(F.col("message"), r"status:([^;]+)", 1),
        )
        .filter(F.col("api_key_name") != "")
    )

    return df.groupBy("api_key_name").agg(
        F.count("*").alias("calls_total"),
        F.count(F.when(F.col("call_status") == "ok", 1)).alias("calls_ok_total"),
        F.count(F.when(F.col("call_status") != "ok", 1)).alias("calls_error_total"),
        # ── janelas de tempo (baseadas no kafka_timestamp da mensagem) ──
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"), 1)
        ).alias("calls_1h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 2 HOURS"), 1)
        ).alias("calls_2h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 12 HOURS"), 1)
        ).alias("calls_12h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 24 HOURS"), 1)
        ).alias("calls_24h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 48 HOURS"), 1)
        ).alias("calls_48h"),
        F.max("kafka_timestamp").alias("last_call_at"),
        F.current_timestamp().alias("computed_at"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 2 — Web3 API Key Consumption → `g_api_keys.web3_keys_consumption`
# MAGIC
# MAGIC Agrega chamadas a provedores Web3 (Infura/Alchemy) por chave, janelas de 1h / 12h / 24h / 48h.
# MAGIC Fonte: mensagens com padrão `API_request;{api_key_name}` (emitidas por `dm_web3_client.py`).

# COMMAND ----------

@dlt.table(
    name="g_api_keys.web3_keys_consumption",
    comment="Gold MV: consumo de API keys Web3 (Alchemy/Infura) por janela de tempo (1h/2h/12h/24h/48h)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_web3_keys_consumption():
    """
    Lê dos silver logs_streaming + logs_batch, filtra mensagens de chamada
    Web3 e agrega por api_key_name + vendor com contadores por janela de tempo.

    Padrões de log emitidos por dm_web3_client.py:
        OK:        API_request;{api_key_name}
        Error:     API_request;{api_key_name};Error:{msg}      (nível ERROR)
        HTTPError: API_request;{api_key_name};HTTPError:{msg}  (nível ERROR)

    A regex usa [^;]+ para extrair apenas o nome da chave, ignorando sufixos
    de erro. O vendor (alchemy/infura) é derivado do nome da chave SSM.
    Uma linha por combinação api_key_name × vendor.
    """
    df = (
        dlt.read("logs_streaming")
        .unionByName(dlt.read("logs_batch"))
        .filter(F.col("message").contains("API_request;"))
        .withColumn(
            "api_key_name",
            # [^;]+ para capturar só o nome da chave (para antes de ;Error: etc.)
            F.regexp_extract(F.col("message"), r"API_request;([^;]+)", 1),
        )
        .withColumn(
            "vendor",
            F.when(F.lower(F.col("api_key_name")).contains("alchemy"), F.lit("alchemy"))
             .when(F.lower(F.col("api_key_name")).contains("infura"),  F.lit("infura"))
             .otherwise(F.lit("unknown")),
        )
        .withColumn(
            "call_status",
            F.when(F.col("message").contains(";Error:"),     F.lit("error"))
             .when(F.col("message").contains(";HTTPError:"), F.lit("http_error"))
             .otherwise(F.lit("ok")),
        )
        .filter(F.col("api_key_name") != "")
    )

    return df.groupBy("api_key_name", "vendor").agg(
        F.count("*").alias("calls_total"),
        F.count(F.when(F.col("call_status") == "ok",     1)).alias("calls_ok_total"),
        F.count(F.when(F.col("call_status") != "ok",     1)).alias("calls_error_total"),
        # ── janelas de tempo (baseadas no kafka_timestamp da mensagem) ──
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"), 1)
        ).alias("calls_1h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 2 HOURS"), 1)
        ).alias("calls_2h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 12 HOURS"), 1)
        ).alias("calls_12h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 24 HOURS"), 1)
        ).alias("calls_24h"),
        F.count(
            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 48 HOURS"), 1)
        ).alias("calls_48h"),
        F.max("kafka_timestamp").alias("last_call_at"),
        F.current_timestamp().alias("computed_at"),
    )
