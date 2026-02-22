import logging
import os

import redis
import requests

from logging import Logger
from typing import Dict, Optional

from pyspark.sql import SparkSession
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import col, count, expr, max, split, window
from pyspark.sql.types import IntegerType, StringType

from utils.spark_utils import SparkUtils


def get_avro_schema_from_sr(schema_registry_url: str, subject: str) -> str:
    """Fetch the latest AVRO schema JSON string for a subject from Confluent SR."""
    url = f"{schema_registry_url}/subjects/{subject}/versions/latest"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()["schema"]


class APIKeyMonitor:

    def __init__(self, logger: Logger, spark: SparkSession):
        self.logger = logger
        self.spark = spark
        self.df_streaming = None

    def config_source(self, src_properties: Dict) -> "APIKeyMonitor":
        self.topic_schema = src_properties["topic_schema"]
        self.kafka_properties = src_properties["kafka_options"]
        self.logger.info(f"Source configured — topic: {self.kafka_properties.get('subscribe')}")
        return self

    def config_sink(self, sink_properties: Dict) -> "APIKeyMonitor":
        self.redis_client = sink_properties["redis_client"]
        self.trigger_time = sink_properties.get("trigger_time", "30 seconds")
        self.output_mode = sink_properties.get("output_mode", "update")
        self.checkpoint_path = sink_properties["checkpoint_path"]
        self.logger.info(f"Sink configured — trigger: {self.trigger_time}, mode: {self.output_mode}")
        return self

    def extract(self) -> "APIKeyMonitor":
        self.df_streaming = (
            self.spark.readStream
            .format("kafka")
            .options(**self.kafka_properties)
            .load()
        )
        return self

    def transform(self) -> "APIKeyMonitor":
        # Confluent AVRO: strip 5-byte magic header (1 magic + 4 schema-id), then deserialize
        self.df_streaming = (
            self.df_streaming
            .withColumn("data", from_avro(expr("substring(value, 6)"), self.topic_schema))
            .withColumn("kafka_timestamp", col("timestamp"))
            .select("kafka_timestamp", "data.*")
            .select("kafka_timestamp", "timestamp", "message")
            .filter(col("message").startswith("API_request"))
            .withColumn("api_key", split(col("message"), ";").getItem(1))
            .select("kafka_timestamp", "timestamp", "api_key")
        )
        window_1d = window(col("kafka_timestamp"), "1 day")
        self.df_streaming = (
            self.df_streaming
            .withWatermark("kafka_timestamp", "1 day")
            .groupBy(col("api_key"), window_1d)
            .agg(
                count("*").alias("count"),
                max("kafka_timestamp").alias("max_timestamp"),
            )
            .select(
                col("api_key").alias("name").cast(StringType()),
                col("window.start").alias("start").cast(StringType()),
                col("window.end").alias("end").cast(StringType()),
                col("count").alias("num_req_1d").cast(IntegerType()),
                col("max_timestamp").alias("last_req").cast(StringType()),
            )
        )
        return self

    def __batch_to_redis(self, batch_df, batch_id):
        for row in batch_df.collect():
            mapping = {
                "start":      row["start"],
                "end":        row["end"],
                "num_req_1d": row["num_req_1d"],
                "last_req":   row["last_req"],
            }
            self.redis_client.hset(row["name"], mapping=mapping)

    def load(self):
        return (
            self.df_streaming.writeStream
            .outputMode("update")
            .foreachBatch(self.__batch_to_redis)
            .option("checkpointLocation", self.checkpoint_path)
            .trigger(processingTime=self.trigger_time)
            .start()
            .awaitTermination()
        )


if __name__ == "__main__":

    APP_NAME              = "STREAMING_0_API_KEYS_WATCHER"
    KAFKA_CLUSTER         = os.getenv("KAFKA_BROKERS")
    TOPIC_SUBSCRIBE       = os.getenv("TOPIC_LOGS", "mainnet.0.application.logs")
    CONSUMER_GROUP        = os.getenv("CONSUMER_GROUP", "cg_api_key_monitor")
    STARTING_OFFSETS      = os.getenv("STARTING_OFFSETS", "latest")
    MAX_OFFSETS_PER_TRIGGER = os.getenv("MAX_OFFSETS_PER_TRIGGER", "1000")
    SCHEMA_REGISTRY_URL   = os.getenv("SCHEMA_REGISTRY_URL")
    TRIGGER_TIME          = os.getenv("TRIGGER_TIME", "30 seconds")
    CHECKPOINT_PATH       = os.getenv("CHECKPOINT_PATH", "/tmp/checkpoints/api_key_monitor")

    REDIS_HOST            = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT            = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB              = int(os.getenv("REDIS_DB_APK_COUNTER", 1))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    LOGGER = logging.getLogger(APP_NAME)

    spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)

    redis_client = redis.StrictRedis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )

    LOGGER.info(f"Fetching AVRO schema for subject '{TOPIC_SUBSCRIBE}-value' from SR")
    avro_schema = get_avro_schema_from_sr(SCHEMA_REGISTRY_URL, f"{TOPIC_SUBSCRIBE}-value")

    src_properties = {
        "topic_schema": avro_schema,
        "kafka_options": {
            "kafka.bootstrap.servers": KAFKA_CLUSTER,
            "subscribe":               TOPIC_SUBSCRIBE,
            "startingOffsets":         STARTING_OFFSETS,
            "group.id":                CONSUMER_GROUP,
            "maxOffsetsPerTrigger":    MAX_OFFSETS_PER_TRIGGER,
        },
    }

    sink_properties = {
        "checkpoint_path": CHECKPOINT_PATH,
        "redis_client":    redis_client,
        "trigger_time":    TRIGGER_TIME,
        "output_mode":     "update",
    }

    LOGGER.info("Starting API Key Monitor")
    _ = (
        APIKeyMonitor(LOGGER, spark)
        .config_source(src_properties)
        .config_sink(sink_properties)
        .extract()
        .transform()
        .load()
    )
