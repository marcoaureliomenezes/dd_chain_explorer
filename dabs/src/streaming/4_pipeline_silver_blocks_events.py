# Databricks notebook source
# Silver DLT Pipeline — Mined Blocks Events
# Lê da Bronze e grava em s_apps.mined_blocks_events.
# Equivalente ao AS-IS: spark-streaming-jobs/src/pyspark/4_job_silver_blocks_events.py

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, IntegerType


BLOCK_EVENT_SCHEMA = StructType([
    StructField("block_number", LongType(), True),
    StructField("block_hash", StringType(), True),
    StructField("block_timestamp", LongType(), True),
    StructField("parent_hash", StringType(), True),
    StructField("transaction_count", IntegerType(), True),
])


@dlt.table(
    name="mined_blocks_events",
    comment="Silver: eventos de blocos minerados na Ethereum Mainnet",
    table_properties={
        "quality": "silver",
        "delta.enableChangeDataFeed": "true",
    },
)
@dlt.expect_or_drop("valid_block_number", "block_number IS NOT NULL")
@dlt.expect_or_drop("valid_block_hash", "block_hash IS NOT NULL")
def silver_mined_blocks_events():
    return (
        dlt.read_stream("kafka_topics_multiplexed")
        .filter(F.col("topic_name") == "mainnet.1.mined_blocks.events")
        .select(
            F.from_json(F.col("value"), BLOCK_EVENT_SCHEMA).alias("data"),
            F.col("kafka_timestamp"),
        )
        .select(
            "data.*",
            "kafka_timestamp",
            F.to_timestamp(F.col("data.block_timestamp")).alias("event_time"),
        )
    )
