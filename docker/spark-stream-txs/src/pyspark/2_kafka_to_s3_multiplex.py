"""
2_kafka_to_s3_multiplex.py — Ingestão multiplexada Kafka → S3 (Parquet)

Lê 5 tópicos Kafka simultaneamente e escreve no S3 em formato Parquet,
particionado por `topic_name`. Os dados ficam prontos para leitura pelo
Databricks Free Edition como external table / DLT pipeline.

Tópicos consumidos:
  - mainnet.0.application.logs
  - mainnet.1.mined_blocks.events
  - mainnet.2.blocks.data
  - mainnet.3.block.txs.hash_id
  - mainnet.4.transactions.data

Estrutura no S3:
  s3a://<bucket>/bronze/kafka_multiplex/
    topic_name=mainnet.0.application.logs/
      part-00000-....snappy.parquet
    topic_name=mainnet.1.mined_blocks.events/
      ...

Env vars obrigatórias:
  KAFKA_BROKERS          — ex: kafka-broker-1:9092
  S3_BUCKET              — ex: dm-chain-explorer-dev-ingestion
  AWS_ACCESS_KEY_ID      — credenciais do IAM user com acesso ao bucket
  AWS_SECRET_ACCESS_KEY  — idem

Env vars opcionais:
  CONSUMER_GROUP         — default: cg_kafka_s3_multiplex
  STARTING_OFFSETS       — default: earliest
  MAX_OFFSETS_PER_TRIGGER — default: 50000
  TRIGGER_TIME           — default: 60 seconds
  CHECKPOINT_PATH        — default: /tmp/checkpoints/kafka_s3_multiplex
"""

import logging
import os

from functools import reduce

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType


# ── Configuration ─────────────────────────────────────────────────────────────

APP_NAME                = "STREAMING_KAFKA_TO_S3_MULTIPLEX"
KAFKA_BROKERS           = os.getenv("KAFKA_BROKERS")
S3_BUCKET               = os.getenv("S3_BUCKET")

AWS_REGION              = os.getenv("AWS_REGION", "sa-east-1")

CONSUMER_GROUP          = os.getenv("CONSUMER_GROUP", "cg_kafka_s3_multiplex")
STARTING_OFFSETS        = os.getenv("STARTING_OFFSETS", "earliest")
MAX_OFFSETS_PER_TRIGGER = os.getenv("MAX_OFFSETS_PER_TRIGGER", "50000")
TRIGGER_TIME            = os.getenv("TRIGGER_TIME", "5 minutes")
CHECKPOINT_PATH         = os.getenv("CHECKPOINT_PATH", f"s3a://{S3_BUCKET}/spark-checkpoints/kafka_s3_multiplex")

TOPICS = [
    "mainnet.0.application.logs",
    "mainnet.1.mined_blocks.events",
    "mainnet.2.blocks.data",
    "mainnet.3.block.txs.hash_id",
    "mainnet.4.transactions.data",
]

OUTPUT_PATH = f"s3a://{S3_BUCKET}/bronze/kafka_multiplex"


# ── Spark session ─────────────────────────────────────────────────────────────

def build_spark_session() -> SparkSession:
    """Create Spark session with S3A (Hadoop AWS) configuration.

    Autenticação AWS via DefaultCredentialsProvider:
      1. ~/.aws/credentials (montado via docker volume: ~/.aws:/root/.aws:ro)
      2. Env vars AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (fallback)
      3. Instance profile / IAM role (quando em EC2/ECS)
    """
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")

    builder = (
        SparkSession.builder
        .master(spark_master)
        .appName(APP_NAME)
        # S3A filesystem — usa DefaultCredentialsProvider (lê ~/.aws)
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain")
        .config("spark.hadoop.fs.s3a.endpoint", f"s3.{AWS_REGION}.amazonaws.com")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true")
    )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


# ── Kafka → S3 pipeline ──────────────────────────────────────────────────────

def read_kafka_topics(spark: SparkSession):
    """Read all topics as a single unioned streaming DataFrame."""
    dfs = []
    for topic in TOPICS:
        df = (
            spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", KAFKA_BROKERS)
            .option("subscribe", topic)
            .option("startingOffsets", STARTING_OFFSETS)
            .option("group.id", CONSUMER_GROUP)
            .option("maxOffsetsPerTrigger", MAX_OFFSETS_PER_TRIGGER)
            .option("failOnDataLoss", "false")
            .load()
            .select(
                F.lit(topic).alias("topic_name"),
                F.col("partition").alias("kafka_partition"),
                F.col("offset").alias("kafka_offset"),
                F.col("timestamp").alias("kafka_timestamp"),
                F.col("key").cast(StringType()).alias("key"),
                F.col("value"),  # keep as binary (Avro with Confluent header)
            )
        )
        dfs.append(df)

    return reduce(lambda a, b: a.union(b), dfs)


def write_to_s3(df):
    """Write streaming DataFrame to S3 as Parquet, partitioned by topic_name."""
    return (
        df.writeStream
        .format("parquet")
        .outputMode("append")
        .partitionBy("topic_name")
        .option("path", OUTPUT_PATH)
        .option("checkpointLocation", CHECKPOINT_PATH)
        .trigger(processingTime=TRIGGER_TIME)
        .start()
    )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger(APP_NAME)

    # Validate required env vars
    if not KAFKA_BROKERS:
        raise RuntimeError("KAFKA_BROKERS env var is required")
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET env var is required")

    logger.info(f"Kafka brokers: {KAFKA_BROKERS}")
    logger.info(f"Topics: {TOPICS}")
    logger.info(f"Output: {OUTPUT_PATH}")
    logger.info(f"Trigger: {TRIGGER_TIME}, offsets/trigger: {MAX_OFFSETS_PER_TRIGGER}")

    spark = build_spark_session()

    logger.info("Starting multiplexed Kafka → S3 streaming pipeline")
    unified_df = read_kafka_topics(spark)
    query = write_to_s3(unified_df)

    logger.info("Pipeline running. Awaiting termination...")
    query.awaitTermination()
