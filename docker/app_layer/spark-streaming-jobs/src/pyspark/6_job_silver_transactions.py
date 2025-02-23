import os
import logging
from logging import Logger
from typing import Dict
from pyspark.sql.functions import col, expr, when
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *
from pyspark.sql import SparkSession


from dm_33_utils.logger_utils import ConsoleLoggingHandler
from dm_33_utils.schema_reg_utils import SchemaRegistryHandler
from utils.spark_utils import SparkUtils
from i_dm_streaming import IDmStreaming



class SilverBlocks(IDmStreaming):
   
  def __init__(self, logger: Logger, spark: SparkSession):
    self.logger = logger
    self.spark = spark
    self.df_streaming = None


  def config_source(self, src_properties: Dict[str, str]):
    self.table_input = src_properties.get("table_input")
    self.max_files_per_trigger = src_properties.get("max_files_per_trigger", "1")
    self.schema_input = src_properties.get("schema")
    self.topic = src_properties.get("topic")
    self.topic_schema = src_properties.get("topic_schema")
    self.logger.info(f"Source configured with table {self.table_input}, max_files_per_trigger {self.max_files_per_trigger}")
    return self
  

  def config_sink( self, tables_output: Dict[str, str],  sink_properties: Dict[str, str]):
    self.silver_txs_fast = tables_output["silver_txs_fast"]
    self.checkpoint_path = sink_properties.get("checkpoint_path")
    self.trigger_time = sink_properties.get("trigger_time")
    self.output_mode = sink_properties.get("output_mode")
    self.logger.info(f"Sink configured with tables {self.silver_txs_fast}")
    self.logger.info(f"Checkpoint path: {self.checkpoint_path}, trigger time: {self.trigger_time}, output mode: {self.output_mode}")
    return self


  def extract(self):
    assert self.table_input, f"Source is not configured. See method {self.config_source.__name__}"
    self.df_streaming = (
      self.spark
        .readStream
        .format("iceberg")
        #.schema(self.topic_schema)
        .option("maxFilesPerTrigger", self.max_files_per_trigger)
        .load(self.table_input)
        .filter(col("topic") == self.topic)
        .select("key","value","partition","offset","ingestion_time","topic", "dat_ref")
        .withColumn("data", from_avro(expr("substring(value, 6)"), self.topic_schema))
        .select("ingestion_time", "data.*")
        )
    return self

    
  def transform(self):
    self.df_streaming = (
      self.df_streaming
        .drop("withdrawals")
        .withColumnRenamed("blockNumber", "block_number")
        .withColumnRenamed("transactionIndex", "transaction_index")
        .withColumnRenamed("gasPrice", "gas_price")
        .withColumnRenamed("from", "from_address")
        .withColumnRenamed("to", "to_address")
        .withColumn("transaction_type", 
                      when(col("input") == "", "P2P")
                      .when((col("input") != "") & (col("to_address") != ""), "CONTRACT_CALL")
                      .otherwise("CONTRACT_CREATION"))
        .withColumn("dat_ref", expr("date_format(ingestion_time, 'yyyy-MM-dd')"))
        .select("ingestion_time", "block_number", "hash", "transaction_type", "transaction_index", "from_address",
                "to_address", "value", "input", "gas", "gas_price", "nonce", "dat_ref"))
    self.df_streaming.printSchema()
    self.spark.table(self.silver_txs_fast).printSchema()
    return self


  def load(self) -> None:
    return (
      self.df_streaming
        .writeStream
        .format("iceberg")
        .outputMode(self.output_mode)
        .option("checkpointLocation", self.checkpoint_path)
        .trigger(processingTime=self.trigger_time)
        .toTable(self.silver_txs_fast)
        .awaitTermination())
  

  def load_to_console(self):
    return (
      self.df_streaming.writeStream
        .outputMode(self.output_mode)
        .format("console")
        .trigger(processingTime=self.trigger_time)
        .option("checkpointLocation", self.checkpoint_path.replace("iceberg", "console"))
        .start()
        .awaitTermination())
  

if __name__ == "__main__":

  APP_NAME = "STREAMING_5_SILVER_TRANSACTIONS"
  SR_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_TXS = os.getenv("TOPIC_TXS")
  BRONZE_TABLE = os.getenv("TABLE_BRONZE")
  SILVER_TXS_FAST = os.getenv("SILVER_TXS_FAST")
  CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH")
  TRIGGER_TIME = os.getenv("TRIGGER_TIME")

  sc_client = SchemaRegistryHandler(SR_URL)
  schema_avro_topic = sc_client.get_schema_by_subject(f"{TOPIC_TXS}-value")
  
  tables_output = { "silver_txs_fast": SILVER_TXS_FAST }
  src_properties = {"table_input": BRONZE_TABLE, "topic": TOPIC_TXS, "topic_schema": schema_avro_topic, "max_files_per_trigger": "1"}
  sink_properties = { "checkpoint_path": CHECKPOINT_PATH, "trigger_time": TRIGGER_TIME, "output_mode": "append"}

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)

  engine = (
    SilverBlocks(LOGGER, spark)
      .config_source(src_properties)
      .config_sink(tables_output, sink_properties)
      .extract()
      .transform()
      .load()
  )
