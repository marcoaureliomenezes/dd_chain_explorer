import os
import logging
from typing import Dict, Self
from pyspark.sql.functions import col, date_format
from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery
from logging import Logger

from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler
from i_dm_streaming import IDmStreaming


class KafkaIngestorMultiplexed(IDmStreaming):
   
  def __init__(self, logger: Logger, spark: SparkSession):
    self.logger = logger
    self.spark = spark
    self.df_streaming = None


  def config_source(self, src_properties: Dict[str, str]) -> Self:
    self.src_properties = src_properties
    self.logger.info(f"Source configured with properties {src_properties}")
    return self
  
  def config_sink( self, tables_output: Dict[str, str],  sink_properties: Dict[str, str]) -> Self:
    self.silver_blocks = tables_output["table_output"]
    self.checkpoint_path = sink_properties.get("checkpoint_path")
    self.trigger_time = sink_properties.get("trigger_time")
    self.output_mode = sink_properties.get("output_mode")
    self.logger.info(f"Sink configured with table {self.silver_blocks}.")
    self.logger.info(f"Table output: {self.silver_blocks}")
    self.logger.info(f"Checkpoint path: {self.checkpoint_path}, trigger time: {self.trigger_time}, output mode: {self.output_mode}")
    return self


  def extract(self) -> Self:
    assert self.src_properties, f"Source is not configured. See method {self.config_source.__name__}"
    self.df_streaming = (
      self.spark.readStream
        .format("kafka")
        .options(**self.src_properties)
        .load())
    return self


  def transform(self) -> Self:
    assert self.df_streaming, f"There is no data to transform. See method {self.extract.__name__}"
    self.df_streaming = (
      self.df_streaming
        .withColumn("dat_ref", date_format(col("timestamp"), "yyyy-MM-dd"))
        .withColumn("ingestion_time", col("timestamp").cast("timestamp"))
        .select("key","value","partition","offset","ingestion_time","topic", "dat_ref"))
    return self


  def load(self) -> None:
    return (
      self.df_streaming
        .writeStream
        .format("iceberg")
        .outputMode(self.output_mode)
        .option("checkpointLocation", self.checkpoint_path)
        .trigger(processingTime=self.trigger_time)
        .toTable(self.silver_blocks)
        .awaitTermination())
  

  def load_to_console(self) -> StreamingQuery:
    return (
      self.df_streaming.writeStream
        .outputMode(self.output_mode)
        .format("console")
        .trigger(processingTime=self.trigger_time)
        .start()
        .awaitTermination())



if __name__ == "__main__":
    
  APP_NAME = "bronze_kafka_topics_multiplexed"
  KAFKA_BROKERS = os.getenv("KAFKA_BROKERS")
  CONSUMER_GROUP = os.getenv("CONSUMER_GROUP")
  STARTING_OFFSETS = os.getenv("STARTING_OFFSETS")
  MAX_OFFSETS_PER_TRIGGER = os.getenv("MAX_OFFSETS_PER_TRIGGER")
  TABLE_BRONZE = os.getenv("TABLE_BRONZE")
  CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH")
  TOPICS = os.getenv("TOPICS")
  
  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())


  src_properties = {
  "kafka.bootstrap.servers": KAFKA_BROKERS,
  "subscribe": TOPICS,
  "startingOffsets": STARTING_OFFSETS,
  "group.id": CONSUMER_GROUP,
  "maxOffsetsPerTrigger": MAX_OFFSETS_PER_TRIGGER,
  'failOnDataLoss': 'false'
  }
  sink_properties = { "checkpoint_path": CHECKPOINT_PATH, "trigger_time": "2 minutes", "output_mode": "append"}
  sink_tables = { "table_output": TABLE_BRONZE }
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  
  _ = (
    KafkaIngestorMultiplexed(LOGGER, spark)
      .config_source(src_properties=src_properties)
      .config_sink(sink_tables, sink_properties)
      .extract()
      .transform()
      .load()
  )

