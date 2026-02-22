# Databricks notebook source
# Silver DLT Pipeline — Transactions
# Lê da Bronze e grava em s_apps.transactions_fast.
# Equivalente ao AS-IS: spark-streaming-jobs/src/pyspark/6_job_silver_transactions.py

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType, DecimalType
)


TX_SCHEMA = StructType([
    StructField("hash", StringType(), True),
    StructField("block_number", LongType(), True),
    StructField("block_hash", StringType(), True),
    StructField("transaction_index", IntegerType(), True),
    StructField("from_address", StringType(), True),
    StructField("to_address", StringType(), True),
    StructField("value", StringType(), True),   # BigInt as string
    StructField("gas", LongType(), True),
    StructField("gas_price", LongType(), True),
    StructField("nonce", LongType(), True),
    StructField("input", StringType(), True),
    StructField("type", IntegerType(), True),
    StructField("max_fee_per_gas", LongType(), True),
    StructField("max_priority_fee_per_gas", LongType(), True),
])


@dlt.table(
    name="transactions_fast",
    comment="Silver: transações Ethereum completas (streaming)",
    table_properties={
        "quality": "silver",
        "delta.enableChangeDataFeed": "true",
    },
    partition_cols=["block_number"],
)
@dlt.expect_or_drop("valid_hash", "hash IS NOT NULL")
@dlt.expect_or_drop("valid_block", "block_number IS NOT NULL")
def silver_transactions():
    return (
        dlt.read_stream("kafka_topics_multiplexed")
        .filter(F.col("topic_name") == "mainnet.4.transactions.data")
        .select(
            F.from_json(F.col("value"), TX_SCHEMA).alias("data"),
            "kafka_timestamp",
        )
        .select(
            "data.*",
            "kafka_timestamp",
        )
    )
