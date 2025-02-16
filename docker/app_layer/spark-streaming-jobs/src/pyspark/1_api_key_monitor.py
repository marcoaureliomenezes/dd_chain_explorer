import os
import redis
import logging

from pyspark.sql import SparkSession
from logging import Logger
from typing import Dict, Optional
from pyspark.sql.functions import col, expr, split, window, count, max
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import StringType, IntegerType

from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler
from dm_33_utils.schema_reg_utils import SchemaRegistryHandler
from i_dm_streaming import IDmStreaming



class APIKeyMonitor(IDmStreaming):
   
  def __init__(self, logger: Logger, spark: SparkSession):
    self.logger = logger
    self.spark = spark
    self.df_streaming = None


  def config_source(self, src_properties: Dict[str, str]):
    self.topic_schema = src_properties["topic_schema"]
    self.kafka_properties = src_properties["kafka_options"]
    self.logger.info(f"Input configured with {self.kafka_properties}")
    return self
  

  def config_sink( self, tables_output: Optional[Dict[str, str]],  sink_properties: Dict[str, str]):
    self.redis_client = sink_properties.get("redis_client")
    self.trigger_time = sink_properties.get("trigger_time")
    self.output_mode = sink_properties.get("output_mode")
    self.logger.info(f"Trigger time: {self.trigger_time}, output mode: {self.output_mode}")
    return self
  

  def extract(self):
    self.df_streaming  = (
      self.spark.readStream
        .format("kafka")
        .options(**self.kafka_properties)
        .load())
    return self


  def transform(self):
    self.df_streaming  = (
      self.df_streaming 
        .withColumn("data", from_avro(expr("substring(value, 6)"), self.topic_schema))
        .withColumn("kafka_timestamp", col("timestamp"))
        .select("kafka_timestamp", "data.*")
        .select("kafka_timestamp", "timestamp", "message")
        .filter(col("message").startswith("API_request"))
        .withColumn("api_key", split(col("message"), ";").getItem(1))
        .select("kafka_timestamp", "timestamp", "api_key")
    )
    window_1D = window(col("kafka_timestamp"), "1 day")
    self.df_streaming = (
      self.df_streaming 
        .withWatermark("kafka_timestamp", "1 day")
        .groupBy(col("api_key"), window_1D)
        .agg(count("*").alias("count"), max("kafka_timestamp").alias("max_timestamp"))
        .select(
          col("api_key").alias("name").cast(StringType()), 
          col("window.start").alias("start").cast(StringType()), 
          col("window.end").alias("end").cast(StringType()), 
          col("count").alias("num_req_1d").cast(IntegerType()),
          col("max_timestamp").alias("last_req").cast(StringType())
        ))
    return self




  def __batch_to_redis(self, batch_df, batch_id):
    for row in batch_df.collect():
      mapping_values = {
        "start": row['start'],
        "end": row['end'],
        "num_req_1d": row['num_req_1d'],
        "last_req": row['last_req']
      }
      self.redis_client.hset(row['name'], mapping=mapping_values)
      

  def load(self):
    return (
      self.df_streaming.writeStream
        .outputMode("update")
        .foreachBatch(self.__batch_to_redis)
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
    
  APP_NAME = "api_keys_consume_monitoring"
  SPARK_URL = os.getenv("SPARK_MASTER_URL")

  KAFKA_CLUSTER = os.getenv("KAFKA_BROKERS")
  TOPIC_SUBSCRIBE = os.getenv("TOPIC_LOGS")
  CONSUMER_GROUP = os.getenv("CONSUMER_GROUP")
  STARTING_OFFSETS = os.getenv("STARTING_OFFSETS")
  MAX_OFFSETS_PER_TRIGGER = os.getenv("MAX_OFFSETS_PER_TRIGGER")
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  
  SCHEMA_REGISTRY_SUBJECT = f"{TOPIC_SUBSCRIBE}-value"

  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  
  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=1, password=REDIS_PASS)
  sc_client = SchemaRegistryHandler(SCHEMA_REGISTRY_URL)
  avro_schema_logs = sc_client.get_schema_by_subject(SCHEMA_REGISTRY_SUBJECT)
 
  src_properties = {
    "topic_schema": avro_schema_logs,
    "kafka_options": {
      "kafka.bootstrap.servers": KAFKA_CLUSTER,
      "subscribe": TOPIC_SUBSCRIBE,
      "startingOffsets": STARTING_OFFSETS,
      "group.id": CONSUMER_GROUP,
      "maxOffsetsPerTrigger": MAX_OFFSETS_PER_TRIGGER 
    }
  }

  sink_properties = {
    "redis_client": redis_client,
    "trigger_time": "2 seconds",
    "output_mode": "update"
  }
  
  _ = (
    APIKeyMonitor(LOGGER, spark)
      .config_source(src_properties)
      .config_sink(tables_output=None, sink_properties=sink_properties)
      .extract()
      .transform()
      .load()

  )