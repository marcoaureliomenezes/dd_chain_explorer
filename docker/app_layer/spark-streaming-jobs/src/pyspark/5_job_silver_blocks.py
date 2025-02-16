import os
import logging
from logging import Logger
from typing import List, Dict, Optional
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr, explode, array_size, to_timestamp
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *

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
    self.silver_blocks = tables_output["silver_blocks"]
    self.silver_blocks_txs = tables_output["silver_blocks_txs"]
    self.checkpoint_path = sink_properties.get("checkpoint_path")
    self.trigger_time = sink_properties.get("trigger_time")
    self.output_mode = sink_properties.get("output_mode")
    self.logger.info(f"Sink configured with tables {self.silver_blocks}, {self.silver_blocks_txs}")
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
        .select("ingestion_time", "data.*").drop("withdrawals")
        )
    return self

    
  def transform(self):
    self.df_streaming = (
        self.df_streaming
        .withColumnRenamed("parentHash", "parent_hash")
        .withColumnRenamed("totalDifficulty", "total_difficulty")
        .withColumnRenamed("baseFeePerGas", "base_fee_per_gas")
        .withColumnRenamed("gasLimit", "gas_limit")
        .withColumnRenamed("gasUsed", "gas_used")
        .withColumnRenamed("logsBloom", "logs_bloom")
        .withColumnRenamed("extraData", "extra_data")
        .withColumnRenamed("transactionsRoot", "transactions_root")
        .withColumnRenamed("stateRoot", "state_root")
        .withColumn("block_timestamp", to_timestamp(col("timestamp")))
        .withColumn("dat_ref", expr("date_format(block_timestamp, 'yyyy-MM-dd')")))
    return self

    



  def __prepare_silver_blocks(self, df_transformed):
    final_columns = [
      "ingestion_time", "block_timestamp", "number", "hash", "parent_hash", "difficulty", "total_difficulty", "nonce", 
      "size", "miner", "base_fee_per_gas", "gas_limit", "gas_used", "logs_bloom", "extra_data", 
      "transactions_root", "state_root", "num_transactions", "dat_ref"]
    df_to_write = (
      df_transformed
        .withColumn("num_transactions", array_size(col("transactions")))
        .select(*final_columns))
    return df_to_write
  

  def __prepare_silver_blocks_txs(self, df_transformed):
    final_columns = ["ingestion_time", "block_timestamp", "block_number", "transaction_id", "dat_ref"]
    df_to_write = (
      df_transformed
      .withColumn("transaction_id", explode(col("transactions")))
      .withColumn("block_number", col("number"))
      .select(*final_columns))
    return df_to_write
  

  def __microbatch_write(self, df, epoch_id):
    df_silver_blocks = self.__prepare_silver_blocks(df)
    df_silver_blocks_txs = self.__prepare_silver_blocks_txs(df)
    df_silver_blocks.writeTo(self.silver_blocks).append()
    df_silver_blocks_txs.writeTo(self.silver_blocks_txs).append()


  def load(self):
    return (
      self.df_streaming.writeStream
        .foreachBatch(self.__microbatch_write)
        .outputMode(self.output_mode)
        .option("checkpointLocation", self.checkpoint_path)
        .trigger(processingTime=self.trigger_time)
        .start()
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

  APP_NAME = "Silver_Blocks"
  SR_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
  TOPIC_BLOCKS = os.getenv("TOPIC_BLOCKS")
  TABLE_SILVER_BLOCKS_TXS = os.getenv("TABLE_SILVER_BLOCKS_TXS")
  CHECKPOINT_PATH = "s3a://spark/checkpoints/iceberg/silver_blocks"
  BRONZE_TABLE = os.getenv("TABLE_BRONZE")

  sc_client = SchemaRegistryHandler(SR_URL)
  schema_avro_topic = sc_client.get_schema_by_subject(f"{TOPIC_BLOCKS}-value")
  

  tables_output = {"silver_blocks": os.getenv("TABLE_SILVER_BLOCKS"), "silver_blocks_txs": os.getenv("TABLE_SILVER_BLOCKS_TXS") }
  src_properties = {"table_input": BRONZE_TABLE, "topic": TOPIC_BLOCKS, "topic_schema": schema_avro_topic, "max_files_per_trigger": "1"}
  sink_properties = { "checkpoint_path": CHECKPOINT_PATH, "trigger_time": "2 seconds", "output_mode": "append"}

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)

  _ = (
    SilverBlocks(logger=LOGGER, spark=spark)
      .config_source(src_properties=src_properties)
      .config_sink(tables_output=tables_output, sink_properties=sink_properties)
      .extract()
      .transform()
      .load()
  )



  # def get_schema_input(self):
  #   return StructType([
  #     StructField('key', BinaryType(), True),
  #     StructField('value', BinaryType(), True),
  #     StructField('partition', IntegerType(), True),
  #     StructField('offset', LongType(), True),
  #     StructField('timestamp', TimestampType(), True),
  #     StructField('topic', StringType(), True),
  #     StructField('dat_ref', StringType(), True)])