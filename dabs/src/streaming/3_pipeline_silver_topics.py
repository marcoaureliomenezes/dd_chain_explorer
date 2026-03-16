# Databricks notebook source
# MAGIC %md
# MAGIC # Silver DLT Pipeline — All Topics
# MAGIC
# MAGIC Pipeline unificado que lê da Bronze multiplex (`b_ethereum.kafka_topics_multiplexed`)
# MAGIC e escreve tabelas Silver individuais (1 por tópico Kafka).
# MAGIC
# MAGIC **Solução para o Schema Registry local:**
# MAGIC Os schemas Avro do Confluent SR estão embutidos neste notebook como JSON strings.
# MAGIC Isso permite deserializar os dados Avro sem acesso ao SR em runtime.
# MAGIC
# MAGIC O campo `value` da Bronze é binário (Confluent wire format):
# MAGIC - Byte 0: magic byte (0x00)
# MAGIC - Bytes 1-4: schema ID (int32 big-endian)
# MAGIC - Bytes 5+: payload Avro binário
# MAGIC
# MAGIC Usamos `substring(value, 6)` para remover o header e `from_avro()` com schema inline.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F
from pyspark.sql.avro.functions import from_avro


# ── Configuration ─────────────────────────────────────────────────────────────

CATALOG       = spark.conf.get("bronze_catalog", "dev")
BRONZE_SCHEMA = spark.conf.get("bronze_schema", "b_ethereum")
BRONZE_TABLE  = spark.conf.get("bronze_table", "kafka_topics_multiplexed")
BRONZE_FQN    = f"{CATALOG}.{BRONZE_SCHEMA}.{BRONZE_TABLE}"


# ── Avro Schemas (extracted from local Confluent Schema Registry) ─────────────
# These are the exact schemas used by the Python producers. Embedding them here
# removes the runtime dependency on the Schema Registry, which is only accessible
# from the local Docker environment.

AVRO_SCHEMA_APP_LOGS = """{
  "type": "record",
  "name": "Application_Logs",
  "namespace": "io.streamr.onchain",
  "fields": [
    {"name": "timestamp", "type": "int"},
    {"name": "logger",    "type": "string"},
    {"name": "level",     "type": "string"},
    {"name": "filename",  "type": "string"},
    {"name": "function_name", "type": "string"},
    {"name": "message",   "type": "string"}
  ]
}"""

AVRO_SCHEMA_MINED_BLOCKS_EVENTS = """{
  "type": "record",
  "name": "mined_block_event_schema",
  "namespace": "io.streamr.onchain",
  "fields": [
    {"name": "block_timestamp", "type": "int"},
    {"name": "block_number",    "type": "int"},
    {"name": "block_hash",      "type": "string"}
  ]
}"""

AVRO_SCHEMA_BLOCKS = """{
  "type": "record",
  "name": "BlockClock",
  "namespace": "io.onchain.streamtxs.avro",
  "fields": [
    {"name": "number",           "type": "long"},
    {"name": "timestamp",        "type": "long"},
    {"name": "hash",             "type": "string"},
    {"name": "parentHash",       "type": "string"},
    {"name": "difficulty",       "type": "long"},
    {"name": "totalDifficulty",  "type": "string"},
    {"name": "nonce",            "type": "string"},
    {"name": "size",             "type": "long"},
    {"name": "miner",            "type": "string"},
    {"name": "baseFeePerGas",    "type": "long"},
    {"name": "gasLimit",         "type": "long"},
    {"name": "gasUsed",          "type": "long"},
    {"name": "logsBloom",        "type": "string"},
    {"name": "extraData",        "type": "string"},
    {"name": "transactionsRoot", "type": "string"},
    {"name": "stateRoot",        "type": "string"},
    {"name": "transactions",     "type": {"type": "array", "items": "string"}},
    {"name": "withdrawals",      "type": {"type": "array", "items": {
      "type": "record", "name": "Withdrawal", "fields": [
        {"name": "index",          "type": "long"},
        {"name": "validatorIndex", "type": "long"},
        {"name": "address",        "type": "string"},
        {"name": "amount",         "type": "long"}
      ]
    }}}
  ]
}"""

AVRO_SCHEMA_TX_HASH_IDS = """{
  "type": "record",
  "name": "transactions_hash_ids",
  "namespace": "io.streamr.onchain",
  "fields": [
    {"name": "tx_hash", "type": "string"}
  ]
}"""

AVRO_SCHEMA_TRANSACTIONS = """{
  "type": "record",
  "name": "Transaction",
  "namespace": "io.streamr.onchain",
  "fields": [
    {"name": "blockHash",        "type": "string"},
    {"name": "blockNumber",      "type": "long"},
    {"name": "hash",             "type": "string"},
    {"name": "transactionIndex", "type": "long"},
    {"name": "from",             "type": "string"},
    {"name": "to",               "type": "string"},
    {"name": "value",            "type": "string"},
    {"name": "input",            "type": "string"},
    {"name": "gas",              "type": "long"},
    {"name": "gasPrice",         "type": "long"},
    {"name": "nonce",            "type": "long"},
    {"name": "v",                "type": "long"},
    {"name": "r",                "type": "string"},
    {"name": "s",                "type": "string"},
    {"name": "type",             "type": "long"},
    {"name": "accessList",       "type": {"type": "array", "items": {
      "type": "record", "name": "accessList", "fields": [
        {"name": "address",     "type": "string"},
        {"name": "storageKeys", "type": {"type": "array", "items": "string"}}
      ]
    }}}
  ]
}"""


# ── Helper ────────────────────────────────────────────────────────────────────

def _read_bronze_avro(topic: str, avro_schema: str):
    """
    Read from Bronze multiplex table, filter by topic, strip the 5-byte
    Confluent header, and deserialize the Avro payload using the given schema.
    Returns a DataFrame with a `parsed` struct column + Kafka metadata.
    """
    return (
        spark.table(BRONZE_FQN)
        .filter(F.col("topic_name") == topic)
        .withColumn("avro_payload", F.expr("substring(value, 6)"))
        .withColumn("parsed", from_avro(F.col("avro_payload"), avro_schema))
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 1 — Application Logs (`mainnet.0.application.logs`)

# COMMAND ----------

@dlt.table(
    name="application_logs",
    comment="Silver: logs estruturados das aplicações Python streaming",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_level", "level IS NOT NULL")
@dlt.expect_or_drop("valid_message", "message IS NOT NULL")
def silver_application_logs():
    df = _read_bronze_avro("mainnet.0.application.logs", AVRO_SCHEMA_APP_LOGS)
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


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 2 — Mined Blocks Events (`mainnet.1.mined_blocks.events`)

# COMMAND ----------

@dlt.table(
    name="mined_blocks_events",
    comment="Silver: eventos de blocos minerados na Ethereum Mainnet",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_block_number", "block_number IS NOT NULL")
@dlt.expect_or_drop("valid_block_hash", "block_hash IS NOT NULL")
def silver_mined_blocks_events():
    df = _read_bronze_avro(
        "mainnet.1.mined_blocks.events", AVRO_SCHEMA_MINED_BLOCKS_EVENTS
    )
    return df.select(
        F.col("parsed.block_number").alias("block_number"),
        F.col("parsed.block_hash").alias("block_hash"),
        F.col("parsed.block_timestamp").alias("block_timestamp"),
        F.to_timestamp(F.col("parsed.block_timestamp")).alias("event_time"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 3 — Blocks Data (`mainnet.2.blocks.data`)

# COMMAND ----------

@dlt.table(
    name="blocks",
    comment="Silver: dados completos dos blocos Ethereum (header + withdrawals)",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_block_number", "block_number IS NOT NULL")
@dlt.expect_or_drop("valid_hash", "block_hash IS NOT NULL")
def silver_blocks():
    df = _read_bronze_avro("mainnet.2.blocks.data", AVRO_SCHEMA_BLOCKS)
    return df.select(
        F.col("parsed.number").alias("block_number"),
        F.col("parsed.hash").alias("block_hash"),
        F.col("parsed.parentHash").alias("parent_hash"),
        F.to_timestamp(F.col("parsed.timestamp")).alias("block_time"),
        F.col("parsed.timestamp").alias("block_timestamp"),
        F.col("parsed.miner").alias("miner"),
        F.col("parsed.difficulty").alias("difficulty"),
        F.col("parsed.totalDifficulty").alias("total_difficulty"),
        F.col("parsed.nonce").alias("nonce"),
        F.col("parsed.size").alias("size"),
        F.col("parsed.baseFeePerGas").alias("base_fee_per_gas"),
        F.col("parsed.gasLimit").alias("gas_limit"),
        F.col("parsed.gasUsed").alias("gas_used"),
        F.col("parsed.logsBloom").alias("logs_bloom"),
        F.col("parsed.extraData").alias("extra_data"),
        F.col("parsed.transactionsRoot").alias("transactions_root"),
        F.col("parsed.stateRoot").alias("state_root"),
        F.size(F.col("parsed.transactions")).alias("transaction_count"),
        F.col("parsed.transactions").alias("transactions"),
        F.col("parsed.withdrawals").alias("withdrawals"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 4 — Transaction Hash IDs (`mainnet.3.block.txs.hash_id`)

# COMMAND ----------

@dlt.table(
    name="transaction_hash_ids",
    comment="Silver: hash IDs de transações por bloco",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_tx_hash", "tx_hash IS NOT NULL")
def silver_transaction_hash_ids():
    df = _read_bronze_avro(
        "mainnet.3.block.txs.hash_id", AVRO_SCHEMA_TX_HASH_IDS
    )
    return df.select(
        F.col("parsed.tx_hash").alias("tx_hash"),
        F.col("key").alias("block_hash"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 5 — Transactions (`mainnet.4.transactions.data`)

# COMMAND ----------

@dlt.table(
    name="transactions",
    comment="Silver: transações Ethereum completas com campos decodificados",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_hash", "tx_hash IS NOT NULL")
@dlt.expect_or_drop("valid_block", "block_number IS NOT NULL")
def silver_transactions():
    df = _read_bronze_avro(
        "mainnet.4.transactions.data", AVRO_SCHEMA_TRANSACTIONS
    )
    return df.select(
        F.col("parsed.hash").alias("tx_hash"),
        F.col("parsed.blockNumber").alias("block_number"),
        F.col("parsed.blockHash").alias("block_hash"),
        F.col("parsed.transactionIndex").alias("transaction_index"),
        # "from" is a reserved word — alias to from_address
        F.col("parsed.`from`").alias("from_address"),
        F.col("parsed.to").alias("to_address"),
        F.col("parsed.value").alias("tx_value"),
        F.col("parsed.input").alias("input_data"),
        F.col("parsed.gas").alias("gas"),
        F.col("parsed.gasPrice").alias("gas_price"),
        F.col("parsed.nonce").alias("nonce"),
        F.col("parsed.v").alias("v"),
        F.col("parsed.r").alias("r"),
        F.col("parsed.s").alias("s"),
        F.col("parsed.type").alias("tx_type"),
        F.col("parsed.accessList").alias("access_list"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )
