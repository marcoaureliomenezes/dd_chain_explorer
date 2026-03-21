# Databricks notebook source
# MAGIC %md
# MAGIC # App Logs DLT Pipeline — Bronze + Silver + Gold
# MAGIC
# MAGIC Pipeline dedicado ao processamento dos logs das aplicações Python on-chain.
# MAGIC Pós-migração Kafka → Kinesis/SQS/Firehose.
# MAGIC
# MAGIC ## Bronze — `b_app_logs`
# MAGIC Auto Loader (cloudFiles) lê NDJSON entregue pelo Firehose no S3:
# MAGIC - `b_app_logs_data` ← Firehose `bronze/app_logs/`
# MAGIC
# MAGIC ## Silver — `s_logs`
# MAGIC Lê da bronze via `dlt.read_stream()` (interno ao pipeline):
# MAGIC - `s_logs.logs_streaming`  ← logs dos jobs de streaming (MINED_BLOCKS_WATCHER, etc.)
# MAGIC - `s_logs.logs_batch`      ← logs dos jobs batch (CONTRACT_TRANSACTIONS_CRAWLER)
# MAGIC
# MAGIC ## Gold — `g_api_keys` (Materialized Views)
# MAGIC - `g_api_keys.etherscan_consumption`   ← consumo de API keys Etherscan por janela de tempo
# MAGIC - `g_api_keys.web3_keys_consumption`   ← consumo de API keys Web3 (Infura/Alchemy) por janela

# COMMAND ----------

import gzip as gzip_lib
import json as json_lib

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType, LongType, StringType, StructField, StructType,
)


# ── Configuration ─────────────────────────────────────────────────────────────

INGESTION_BUCKET = spark.conf.get("ingestion.s3.bucket", "dm-chain-explorer-dev-ingestion")
S3_RAW_BASE      = f"s3://{INGESTION_BUCKET}/raw"

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

# COMMAND ----------


# ── CloudWatch Logs schema & UDF ──────────────────────────────────────────────

_CW_EVENT_SCHEMA = ArrayType(StructType([
    StructField("timestamp",     LongType(),   True),
    StructField("message",       StringType(), True),
    StructField("log_group",     StringType(), True),
    StructField("log_stream",    StringType(), True),
]))


@F.udf(returnType=_CW_EVENT_SCHEMA)
def _extract_cw_log_events(content):
    """
    Decompress double-gzipped CloudWatch Logs Firehose payload and
    return individual log events.

    File layout: outer gzip (Firehose) → inner gzip (CW Logs)
    → concatenated JSON envelopes with logEvents arrays.
    """
    if content is None:
        return []
    try:
        inner = gzip_lib.decompress(bytes(content))
    except Exception:
        return []
    try:
        text = gzip_lib.decompress(inner).decode("utf-8")
    except Exception:
        try:
            text = inner.decode("utf-8")
        except Exception:
            return []

    events = []
    decoder = json_lib.JSONDecoder()
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx] in " \n\r\t":
            idx += 1
        if idx >= len(text):
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            idx = end
            if obj.get("messageType") == "DATA_MESSAGE":
                lg = obj.get("logGroup", "")
                ls = obj.get("logStream", "")
                for le in obj.get("logEvents", []):
                    events.append({
                        "timestamp":  le.get("timestamp"),
                        "message":    le.get("message", ""),
                        "log_group":  lg,
                        "log_stream": ls,
                    })
        except Exception:
            idx += 1
    return events


# ── Auto Loader Helper ─────────────────────────────────────────────────────────

def _auto_loader_cwlogs(stream_name: str):
    """
    Auto Loader reader for CloudWatch Logs files delivered by Firehose.

    Files are double-gzipped (Firehose GZIP + CW Logs inner gzip).
    Uses binaryFile format + UDF to decompress and extract events,
    then parses each log event message as JSON.
    """
    path = f"{S3_RAW_BASE}/{stream_name}/"
    raw = (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .option("cloudFiles.schemaLocation",
                f"s3://{INGESTION_BUCKET}/checkpoints/schemas/{stream_name}")
        .load(path)
    )
    return (
        raw
        .withColumn("events", _extract_cw_log_events(F.col("content")))
        .select(F.explode("events").alias("evt"))
        .select(
            F.col("evt.timestamp").alias("timestamp"),
            F.col("evt.log_group").alias("log_group"),
            F.col("evt.log_stream").alias("log_stream"),
            F.col("evt.message").alias("raw_message"),
        )
        .withColumn("_parsed", F.from_json("raw_message", "timestamp LONG, logger STRING, level STRING, filename STRING, function_name STRING, message STRING"))
        .select(
            F.col("timestamp"),
            F.coalesce(F.col("_parsed.logger"),  F.col("log_stream")).alias("logger"),
            F.coalesce(F.col("_parsed.level"),   F.lit("INFO")).alias("level"),
            F.col("_parsed.filename").alias("filename"),
            F.col("_parsed.function_name").alias("function_name"),
            F.coalesce(F.col("_parsed.message"), F.col("raw_message")).alias("message"),
            F.col("log_group"),
            F.col("log_stream"),
        )
    )


# ════════════════════════════════════════════════════════════════════════════
# BRONZE LAYER
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------
# MAGIC %md
# MAGIC ## Bronze — `b_app_logs_data`
# MAGIC
# MAGIC Auto Loader lê NDJSON entregue pelo Firehose (CloudWatch Logs → S3).
# MAGIC Cada registro JSON contém: `timestamp`, `logger`, `level`, `filename`,
# MAGIC `function_name`, `message`.

# COMMAND ----------

@dlt.table(
    name="b_app_logs_data",
    comment="Bronze: logs das aplicações on-chain via CloudWatch → Firehose → S3 (NDJSON)",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
    },
)
def bronze_app_logs_data():
    return (
        _auto_loader_cwlogs("app_logs")
        .withColumn("_ingested_at", F.current_timestamp())
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
    df = dlt.read_stream("b_app_logs_data")
    return (
        df.select(
            F.col("timestamp").alias("event_ts_epoch"),
            F.to_timestamp(F.col("timestamp")).alias("event_time"),
            F.col("logger"),
            F.col("level"),
            F.col("filename"),
            F.col("function_name"),
            F.col("message"),
            F.col("_ingested_at"),
        )
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
    df = dlt.read_stream("b_app_logs_data")
    return (
        df.select(
            F.col("timestamp").alias("event_ts_epoch"),
            F.to_timestamp(F.col("timestamp")).alias("event_time"),
            F.col("logger"),
            F.col("level"),
            F.col("filename"),
            F.col("function_name"),
            F.col("message"),
            F.col("_ingested_at"),
        )
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
    Janelas: 1h, 2h, 12h, 24h, 48h (relativas ao _ingested_at da mensagem).
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
        # ── janelas de tempo (baseadas no _ingested_at da mensagem) ──
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"), 1)
        ).alias("calls_1h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 2 HOURS"), 1)
        ).alias("calls_2h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 12 HOURS"), 1)
        ).alias("calls_12h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 24 HOURS"), 1)
        ).alias("calls_24h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 48 HOURS"), 1)
        ).alias("calls_48h"),
        F.max("_ingested_at").alias("last_call_at"),
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
        # ── janelas de tempo (baseadas no _ingested_at da mensagem) ──
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"), 1)
        ).alias("calls_1h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 2 HOURS"), 1)
        ).alias("calls_2h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 12 HOURS"), 1)
        ).alias("calls_12h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 24 HOURS"), 1)
        ).alias("calls_24h"),
        F.count(
            F.when(F.col("_ingested_at") >= F.expr("current_timestamp() - INTERVAL 48 HOURS"), 1)
        ).alias("calls_48h"),
        F.max("_ingested_at").alias("last_call_at"),
        F.current_timestamp().alias("computed_at"),
    )
