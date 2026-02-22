# Databricks notebook source
# Silver DLT Pipeline — Application Logs
# Lê da Bronze (kafka_topics_multiplexed) e grava em s_logs.apps_logs_fast.
# Equivalente ao AS-IS: spark-streaming-jobs/src/pyspark/3_job_silver_apps_logs.py

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType
import json


LOG_SCHEMA = StructType([
    StructField("level", StringType(), True),
    StructField("logger", StringType(), True),
    StructField("message", StringType(), True),
    StructField("timestamp", LongType(), True),
    StructField("job_name", StringType(), True),
    StructField("api_key", StringType(), True),
])


@dlt.table(
    name="apps_logs_fast",
    comment="Silver: logs estruturados de aplicações Python Streaming",
    table_properties={
        "quality": "silver",
        "delta.enableChangeDataFeed": "true",
    },
    partition_cols=["job_name"],
)
@dlt.expect_or_drop("valid_level", "level IS NOT NULL")
@dlt.expect_or_drop("valid_message", "message IS NOT NULL")
def silver_apps_logs():
    return (
        dlt.read_stream("kafka_topics_multiplexed")
        .filter(F.col("topic_name") == "mainnet.0.application.logs")
        .select(
            F.from_json(F.col("value"), LOG_SCHEMA).alias("data"),
            F.col("timestamp").alias("kafka_timestamp"),
        )
        .select(
            "data.*",
            F.col("kafka_timestamp"),
            F.to_timestamp(F.col("data.timestamp") / 1000).alias("event_time"),
        )
    )
