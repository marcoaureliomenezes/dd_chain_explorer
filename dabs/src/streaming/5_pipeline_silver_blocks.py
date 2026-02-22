# Databricks notebook source
# Silver DLT Pipeline — Full Block Data
# Lê da Bronze e grava em s_apps.blocks_fast.
# Equivalente ao AS-IS: spark-streaming-jobs/src/pyspark/5_job_silver_blocks.py

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType, ArrayType
)


BLOCK_SCHEMA = StructType([
    StructField("number", LongType(), True),
    StructField("hash", StringType(), True),
    StructField("parent_hash", StringType(), True),
    StructField("timestamp", LongType(), True),
    StructField("miner", StringType(), True),
    StructField("difficulty", LongType(), True),
    StructField("total_difficulty", StringType(), True),
    StructField("size", IntegerType(), True),
    StructField("gas_used", LongType(), True),
    StructField("gas_limit", LongType(), True),
    StructField("transaction_count", IntegerType(), True),
    StructField("base_fee_per_gas", LongType(), True),
])


@dlt.table(
    name="blocks_fast",
    comment="Silver: dados completos dos blocos Ethereum (streaming)",
    table_properties={
        "quality": "silver",
        "delta.enableChangeDataFeed": "true",
    },
)
@dlt.expect_or_drop("valid_block_number", "number IS NOT NULL")
def silver_blocks():
    return (
        dlt.read_stream("kafka_topics_multiplexed")
        .filter(F.col("topic_name") == "mainnet.2.blocks.data")
        .select(
            F.from_json(F.col("value"), BLOCK_SCHEMA).alias("data"),
            "kafka_timestamp",
        )
        .select(
            "data.*",
            "kafka_timestamp",
            F.to_timestamp(F.col("data.timestamp")).alias("event_time"),
        )
    )
