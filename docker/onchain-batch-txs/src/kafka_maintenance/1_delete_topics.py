import os
import logging







































































































































































































































































    )        F.current_timestamp().alias("computed_at"),        F.max("kafka_timestamp").alias("last_call_at"),        ).alias("calls_48h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 48 HOURS"), 1)        F.count(        ).alias("calls_24h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 24 HOURS"), 1)        F.count(        ).alias("calls_12h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 12 HOURS"), 1)        F.count(        ).alias("calls_1h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"), 1)        F.count(        F.count("*").alias("calls_total"),    return df.groupBy("api_key_name").agg(    )        .filter(F.col("api_key_name") != "")        )            F.regexp_extract(F.col("message"), r"API_request;(.+)", 1),            "api_key_name",        .withColumn(        .filter(F.col("message").startswith("API_request;"))        .unionByName(dlt.read("logs_batch"))        dlt.read("logs_streaming")    df = (    """        API_request;{api_key_name}    Padrão de log (emitido por dm_web3_client.py):    Web3 e agrega por api_key_name com contadores por janela de tempo.    Lê dos silver logs_streaming + logs_batch, filtra mensagens de chamada    """def gold_web3_keys_consumption():)    },        "pipelines.autoOptimize.managed": "true",        "quality": "gold",    table_properties={    comment="Gold MV: consumo de API keys Web3 (Infura/Alchemy) por janela de tempo (1h/12h/24h/48h)",    name="g_api_keys.web3_keys_consumption",@dlt.table(# COMMAND ----------# MAGIC Fonte: mensagens com padrão `API_request;{api_key_name}` (emitidas por `dm_web3_client.py`).# MAGIC Agrega chamadas a provedores Web3 (Infura/Alchemy) por chave, janelas de 1h / 12h / 24h / 48h.# MAGIC# MAGIC ## Gold 2 — Web3 API Key Consumption → `g_api_keys.web3_keys_consumption`# MAGIC %md# COMMAND ----------    )        F.current_timestamp().alias("computed_at"),        F.max("kafka_timestamp").alias("last_call_at"),        ).alias("calls_48h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 48 HOURS"), 1)        F.count(        ).alias("calls_24h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 24 HOURS"), 1)        F.count(        ).alias("calls_12h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 12 HOURS"), 1)        F.count(        ).alias("calls_1h"),            F.when(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"), 1)        F.count(        F.count("*").alias("calls_total"),    return df.groupBy("api_key_name").agg(    )        .filter(F.col("api_key_name") != "")        )            F.regexp_extract(F.col("message"), r"status:([^;]+)", 1),            "status",        .withColumn(        )            F.regexp_extract(F.col("message"), r"action:([^;]+)", 1),            "action",        .withColumn(        )            F.regexp_extract(F.col("message"), r"api_key_name:([^;]+)", 1),            "api_key_name",        .withColumn(        .filter(F.col("message").contains("etherscan;api_call;"))        .unionByName(dlt.read("logs_batch"))        dlt.read("logs_streaming")    df = (    """        etherscan;api_call;api_key_name:{name};action:{action};status:{status};request_count:{n}    Padrão de log (emitido por EtherscanClient._track_call):    Etherscan e agrega por api_key_name com contadores por janela de tempo.    Lê dos silver logs_streaming + logs_batch, filtra mensagens de chamada    """def gold_etherscan_consumption():)    },        "pipelines.autoOptimize.managed": "true",        "quality": "gold",    table_properties={    comment="Gold MV: consumo de API keys Etherscan por janela de tempo (1h/12h/24h/48h)",    name="g_api_keys.etherscan_consumption",@dlt.table(# COMMAND ----------# MAGIC Fonte: mensagens com padrão `etherscan;api_call;api_key_name:{name};action:{act};...`# MAGIC Agrega chamadas à API Etherscan por chave, janelas de 1h / 12h / 24h / 48h.# MAGIC# MAGIC ## Gold 1 — Etherscan API Key Consumption → `g_api_keys.etherscan_consumption`# MAGIC %md# COMMAND ----------# ════════════════════════════════════════════════════════════════════════════# GOLD — Materialized Views de consumo de API keys# ════════════════════════════════════════════════════════════════════════════    )        .filter(F.col("logger").isin(BATCH_APP_NAMES))        _parse_app_logs_from_bronze()    return (def silver_logs_batch():@dlt.expect_or_drop("valid_message", "message IS NOT NULL")@dlt.expect_or_drop("valid_level",   "level IS NOT NULL"))    },        "pipelines.autoOptimize.managed": "true",        "quality": "silver",    table_properties={    comment="Silver: logs das aplicações batch on-chain",    name="logs_batch",@dlt.table(# COMMAND ----------# MAGIC Logs dos jobs batch: `CONTRACT_TRANSACTIONS_CRAWLER`.# MAGIC# MAGIC ## Silver 2 — Batch App Logs → `s_logs.logs_batch`# MAGIC %md# COMMAND ----------    )        .filter(F.col("logger").isin(STREAMING_APP_NAMES))        _parse_app_logs_from_bronze()    return (def silver_logs_streaming():@dlt.expect_or_drop("valid_message", "message IS NOT NULL")@dlt.expect_or_drop("valid_level",   "level IS NOT NULL"))    },        "pipelines.autoOptimize.managed": "true",        "quality": "silver",    table_properties={    comment="Silver: logs das aplicações de streaming on-chain",    name="logs_streaming",@dlt.table(# COMMAND ----------# MAGIC `BLOCK_DATA_CRAWLER`, `MINED_TXS_CRAWLER`, `TXS_INPUT_DECODER`.# MAGIC Logs dos jobs de streaming: `MINED_BLOCKS_WATCHER`, `ORPHAN_BLOCKS_WATCHER`,# MAGIC# MAGIC ## Silver 1 — Streaming App Logs → `s_logs.logs_streaming`# MAGIC %md# COMMAND ----------# ════════════════════════════════════════════════════════════════════════════# SILVER LAYER# ════════════════════════════════════════════════════════════════════════════    )        F.col("kafka_offset"),        F.col("kafka_partition"),        F.col("kafka_timestamp"),        F.col("parsed.message").alias("message"),        F.col("parsed.function_name").alias("function_name"),        F.col("parsed.filename").alias("filename"),        F.col("parsed.level").alias("level"),        F.col("parsed.logger").alias("logger"),        F.to_timestamp(F.col("parsed.timestamp")).alias("event_time"),        F.col("parsed.timestamp").alias("event_ts_epoch"),    return df.select(    )        .withColumn("parsed", from_avro(F.col("avro_payload"), AVRO_SCHEMA_APP_LOGS))        .withColumn("avro_payload", F.expr("substring(value, 6)"))        .filter(F.col("topic_name") == TOPIC_APP_LOGS)        spark.readStream.table(f"{CATALOG}.b_ethereum.kafka_topics_multiplexed")    df = (    """    O payload Kafka tem 5 bytes de cabeçalho do Schema Registry antes do Avro.    apenas o tópico de logs de aplicação e decodifica o payload Avro.    Lê de kafka_topics_multiplexed (bronze, pipeline dm-ethereum), filtra    """def _parse_app_logs_from_bronze():# ── Helper ────────────────────────────────────────────────────────────────────}"""  ]    {"name": "message",       "type": "string"}    {"name": "function_name", "type": "string"},    {"name": "filename",      "type": "string"},    {"name": "level",         "type": "string"},    {"name": "logger",        "type": "string"},    {"name": "timestamp",     "type": "int"},  "fields": [  "namespace": "io.streamr.onchain",  "name": "Application_Logs",  "type": "record",AVRO_SCHEMA_APP_LOGS = """{# ── Avro Schema ───────────────────────────────────────────────────────────────]    "CONTRACT_TRANSACTIONS_CRAWLER",BATCH_APP_NAMES = []    "TXS_INPUT_DECODER",    "MINED_TXS_CRAWLER",    "BLOCK_DATA_CRAWLER",    "ORPHAN_BLOCKS_WATCHER",    "MINED_BLOCKS_WATCHER",STREAMING_APP_NAMES = [# APP_NAME constants — usados como valor do campo `logger` nas mensagens de logTOPIC_APP_LOGS = "mainnet.0.application.logs"# Tópico Kafka de logs de aplicaçãoCATALOG = spark.conf.get("catalog", "dd_chain_explorer_dev")# ── Configuration ─────────────────────────────────────────────────────────────from pyspark.sql.avro.functions import from_avrofrom pyspark.sql.types import StringTypefrom pyspark.sql import functions as Fimport dlt# COMMAND ----------# MAGIC - `g_api_keys.web3_keys_consumption`   ← consumo de API keys Web3 (Infura/Alchemy) por janela# MAGIC - `g_api_keys.etherscan_consumption`   ← consumo de API keys Etherscan por janela de tempo# MAGIC ## Gold — `g_api_keys` (Materialized Views)# MAGIC# MAGIC - `s_logs.logs_batch`      ← logs dos jobs batch (CONTRACT_TRANSACTIONS_CRAWLER)# MAGIC - `s_logs.logs_streaming`  ← logs dos jobs de streaming (MINED_BLOCKS_WATCHER, etc.)# MAGIC ## Silver — `s_logs`# MAGIC# MAGIC filtra o tópico `mainnet.0.application.logs`, decodifica o Avro e produz:# MAGIC Lê da tabela bronze `b_ethereum.kafka_topics_multiplexed` (produzida por `dm-ethereum`),# MAGIC Pipeline dedicado ao processamento dos logs das aplicações Python on-chain.# MAGIC# MAGIC # App Logs DLT Pipeline — Silver + Goldfrom argparse import ArgumentParser, FileType
from configparser import ConfigParser
from dm_kafka_admin import DMClusterAdmin

from dm_chain_utils.dm_logger import ConsoleLoggingHandler


if __name__ == "__main__":

    NETWORK = os.environ["NETWORK"]
    KAFKA_BROKER = os.getenv("KAFKA_BROKERS")
    parser = ArgumentParser(description=f'Stream transactions network')
    parser.add_argument('config_file', type=FileType('r'), help='Config file')
    parser.add_argument('--dry-run', type=str, default="true", help='Dry Run')
    args = parser.parse_args()
    config = ConfigParser()
    config.read_file(args.config_file)
    dry_run = args.dry_run

    logger = logging.getLogger("KAFKA_ADMIN")
    logger.setLevel(logging.INFO)
    ConsoleLoggingHandler = ConsoleLoggingHandler()
    logger.addHandler(ConsoleLoggingHandler)
    kafka_conf = {"bootstrap.servers": KAFKA_BROKER}
    kafka_admin = DMClusterAdmin(logger, kafka_conf)

    topics = [
      # "topic.application.logs",
      "topic.mined_blocks.events",
      "topic.blocks_data",
      "topic.block_txs.hash_ids",
      "topic.txs.raw_data",
      "topic.txs.input_decoded"
    ]

    print(dry_run)
    topic_configs = config["topic.general.config"]
    for topic in topics:
      topic_name = f"{NETWORK}.{config[topic]['name']}"
      kafka_admin.delete_topic(topic_name, dry_run=dry_run)


