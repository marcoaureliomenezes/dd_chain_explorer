# Databricks notebook source
# MAGIC %md
# Bronze Multiplex DLT Pipeline
#
# Dual-source pipeline:
#   - **PROD** (`source.type = kafka`): consome Kafka MSK diretamente (streaming)
#   - **DEV**  (`source.type = s3`): lê Parquet do S3, ingestado pelo job Spark local
#
# A tabela de destino é a mesma: `b_fast.kafka_topics_multiplexed`

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StringType


# ── Configuration ─────────────────────────────────────────────────────────────

SOURCE_TYPE     = spark.conf.get("source.type", "kafka")       # "kafka" or "s3"
KAFKA_BOOTSTRAP = spark.conf.get("kafka.bootstrap.servers", "")
MSK_IAM_AUTH    = spark.conf.get("kafka.msk.iam.auth", "false").lower() == "true"
S3_PATH         = spark.conf.get("s3.ingestion.path", "")

TOPICS = [
    "mainnet.0.application.logs",
    "mainnet.1.mined_blocks.events",
    "mainnet.2.blocks.data",
    "mainnet.3.block.txs.hash_id",
    "mainnet.4.transactions.data",
]


# ── Kafka source (PROD) ──────────────────────────────────────────────────────

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


def _read_from_kafka():
    """Lê todos os tópicos Kafka e retorna um único DataFrame unificado (streaming)."""
    from functools import reduce

    dfs = []
    for topic in TOPICS:
        df = (
            _kafka_reader(topic)
            .load()
            .select(
                F.lit(topic).alias("topic_name"),
                F.col("partition").alias("kafka_partition"),
                F.col("offset").alias("kafka_offset"),
                F.col("timestamp").alias("kafka_timestamp"),
                F.col("key").cast(StringType()).alias("key"),
                F.col("value").cast(StringType()).alias("value"),
            )
        )
        dfs.append(df)

    return reduce(lambda a, b: a.union(b), dfs)


# ── S3 Parquet source (DEV) ──────────────────────────────────────────────────

def _read_from_s3():
    """
    Lê dados Parquet do S3 (gerados pelo job Spark local kafka-to-s3).
    Usa Auto Loader (cloudFiles) para ingestão incremental.
    Estrutura esperada: s3://<bucket>/bronze/kafka_multiplex/topic_name=<topic>/...parquet
    """
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation", f"{S3_PATH}/_schema")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(S3_PATH)
        .select(
            F.col("topic_name"),
            F.col("kafka_partition"),
            F.col("kafka_offset"),
            F.col("kafka_timestamp"),
            F.col("key"),
            F.col("value"),
        )
    )


# ── DLT table definition ─────────────────────────────────────────────────────

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
    Source dinâmico baseado na configuração `source.type`:
      - kafka: lê dos tópicos Kafka MSK (PROD)
      - s3:    lê Parquet do S3 via Auto Loader (DEV)
    """
    if SOURCE_TYPE == "s3":
        return _read_from_s3()
    else:
        return _read_from_kafka()
