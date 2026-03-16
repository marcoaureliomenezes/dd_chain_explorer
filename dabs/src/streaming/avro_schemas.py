# Databricks notebook source
# MAGIC %md
# MAGIC # Avro Schemas — Centralização dos Schemas de Tópicos Kafka
# MAGIC
# MAGIC Este notebook é carregado via `%run ./avro_schemas` nos pipelines DLT
# MAGIC (`4_pipeline_ethereum.py` and `5_pipeline_app_logs.py`) para evitar duplicação
# MAGIC de schemas Avro entre notebooks (TODO-P07).
# MAGIC
# MAGIC **Schemas disponibilizados:**
# MAGIC - `AVRO_SCHEMA_APP_LOGS`            ← `mainnet.0.application.logs`
# MAGIC - `AVRO_SCHEMA_MINED_BLOCKS_EVENTS` ← `mainnet.1.mined_blocks.events`
# MAGIC - `AVRO_SCHEMA_BLOCKS`              ← `mainnet.2.blocks.data`
# MAGIC - `AVRO_SCHEMA_TX_HASH_IDS`         ← `mainnet.3.block.txs.hash_id`
# MAGIC - `AVRO_SCHEMA_TRANSACTIONS`        ← `mainnet.4.transactions.data`
# MAGIC - `AVRO_SCHEMA_INPUT_DECODED`       ← `mainnet.5.transactions.input_decoded`
# MAGIC
# MAGIC **Formato:** Confluent Wire Format — 5 bytes de header seguidos pelo payload Avro.
# MAGIC Para deserializar: `substring(value, 6)` remove o header antes de `from_avro()`.

# COMMAND ----------

# ── Avro Schemas ──────────────────────────────────────────────────────────────
# Schemas embutidos eliminam dependência do Schema Registry em runtime no DLT.
# Fonte: arquivos em docker/onchain-stream-txs/src/schemas/*.json

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
    {"name": "transactions", "type": {"type": "array", "items": "string"}},
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

AVRO_SCHEMA_INPUT_DECODED = """{
  "type": "record",
  "name": "Input_Transaction",
  "namespace": "io.streamr.onchain",
  "fields": [
    {"name": "tx_hash",          "type": "string"},
    {"name": "contract_address", "type": "string"},
    {"name": "method",           "type": "string"},
    {"name": "parms",            "type": "string"},
    {"name": "decode_type",      "type": "string"}
  ]
}"""
