# Databricks notebook source
# MAGIC %md
# Bronze Multiplex DLT Pipeline
# Consome todos os tópicos Kafka e grava na tabela Bronze kafka_topics_multiplexed.
# Equivalente ao AS-IS: spark-streaming-jobs/src/pyspark/2_job_bronze_multiplex.py

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, TimestampType, LongType


KAFKA_BOOTSTRAP = spark.conf.get("kafka.bootstrap.servers")
MSK_IAM_AUTH    = spark.conf.get("kafka.msk.iam.auth", "false").lower() == "true"

TOPICS = [
    "mainnet.0.application.logs",
    "mainnet.1.mined_blocks.events",
    "mainnet.2.blocks.data",
    "mainnet.3.block.txs.hash_id",
    "mainnet.4.transactions.data",
]


def _kafka_reader(topic: str):
    """Retorna um Spark Streaming reader para um tópico Kafka específico."""
    options = {
        "kafka.bootstrap.servers": KAFKA_BOOTSTRAP,
        "subscribe": topic,
        "startingOffsets": "latest",
        "failOnDataLoss": "false",
    }

    if MSK_IAM_AUTH:
        options.update({
            "kafka.security.protocol": "SASL_SSL",
            "kafka.sasl.mechanism": "AWS_MSK_IAM",
            "kafka.sasl.jaas.config": (
                "software.amazon.msk.auth.iam.IAMLoginModule required;"
            ),
            "kafka.sasl.client.callback.handler.class": (
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler"
            ),
        })

    return spark.readStream.format("kafka").options(**options)


@dlt.table(
    name="kafka_topics_multiplexed",
    comment="Tabela Bronze: todos os tópicos Kafka multiplexados em uma única tabela",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
    },
    partition_cols=["topic_name"],
)
def bronze_multiplex():
    """
    Lê todos os tópicos de interesse do Kafka e unifica em uma única tabela Bronze.
    Colunas: topic_name, partition, offset, timestamp, key, value (raw bytes → string)
    """
    dfs = []
    for topic in TOPICS:
        df = (
            _kafka_reader(topic)
            .load()
            .select(
                F.lit(topic).alias("topic_name"),
                F.col("partition"),
                F.col("offset"),
                F.col("timestamp"),
                F.col("key").cast(StringType()).alias("key"),
                F.col("value").cast(StringType()).alias("value"),
            )
        )
        dfs.append(df)

    from functools import reduce
    return reduce(lambda a, b: a.union(b), dfs)
