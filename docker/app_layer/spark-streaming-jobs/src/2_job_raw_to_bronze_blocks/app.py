import os
import redis

from pyspark.sql.functions import col, expr, split, window, count, max
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import StringType, IntegerType

from utils.spark_utils import SparkUtils
from utils.schema_registry_utils import SchemaRegistryUtils

class APIKeyMonitor:
   
  def __init__(self, spark, kafka_options, redis_client):
    self.spark = spark
    self.redis_client = redis_client
    self.kafka_options = kafka_options


  def extract_data(self, avro_schema: str):
    df_simple_transactions = (
      self.spark
        .readStream
        .format("kafka")
        .options(**self.kafka_options)
        .load()
        .withColumn("offset", col("offset").cast(IntegerType()))
        .withColumn("timestamp", col("timestamp").cast(StringType()))
        .withColumnRenamed("key", "topic_key")
        .withColumnRenamed("value", "topic_value")
        .withColumnRenamed("timestamp", "kafka_timestamp")
        .withColumnRenamed("partition", "kafka_partition")
        .select("topic_key", "topic_value",  "kafka_partition", "offset",
                "kafka_timestamp", "timestamptype", "topic")

    )
    return df_simple_transactions


  def transform_data(self, df_stream):
    
    return df_stream


  def load_data_to_console(self, df_transformed):
    write_stream_query = (
      df_transformed
        .writeStream
        .outputMode("append")
        .format("console")
        .start()
        .awaitTermination()
    )
    return write_stream_query


  def __batch_to_redis(self, batch_df, batch_id):
    for row in batch_df.collect():
      mapping_values = {
        "start": row['start'],
        "end": row['end'],
        "num_req_1d": row['num_req_1d'],
        "last_req": row['last_req']
      }
      self.redis_client.hset(row['name'], mapping=mapping_values)
      

  def load_data_to_redis(self, df_transformed):
      query = (
        df_transformed
          .writeStream
          .outputMode("update")
          .foreachBatch(self.__batch_to_redis)
          .start()
          .awaitTermination()
      )
      return query
  
  # append data to a iceberg table
  def load_data_to_bronze(self, df_transformed):
    query = (
      df_transformed
        .writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", "hdfs://namenode:9000/dm_lakehouse/checkpoint/all_topics")
        .toTable("bronze_fast.all_topics")
    )
    return query



if __name__ == "__main__":
    
  APP_NAME = "Handle_Simple_Transactions"
  SPARK_URL = os.getenv("SPARK_MASTER_URL")

  KAFKA_CLUSTER = os.getenv("KAFKA_BROKERS")
  TOPIC_SUBSCRIBE = os.getenv("TOPIC_LOGS")
  CONSUMER_GROUP = os.getenv("CG_API_KEY_CONSUME") + "algo"
  STARTING_OFFSETS = os.getenv("STARTING_OFFSETS")
  MAX_OFFSETS_PER_TRIGGER = os.getenv("MAX_OFFSETS_PER_TRIGGER")

  SCHEMA_REGISTRY_URL = "http://schema-registry:8081"
  SCHEMA_REGISTRY_SUBJECT = "mainnet.application.logs-value"

  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  
  spark = SparkUtils.get_spark_session(APP_NAME)
  redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=1, password=REDIS_PASS)
  kafka_options = {
    "kafka.bootstrap.servers": KAFKA_CLUSTER,
    "subscribe": "mainnet.mined.block.metadata,mainnet.mined.txs.token.transfer",
    "startingOffsets": STARTING_OFFSETS,
    "group.id": CONSUMER_GROUP,
    "maxOffsetsPerTrigger": MAX_OFFSETS_PER_TRIGGER 
  }

  engine = APIKeyMonitor(spark, kafka_options, redis_client)
  sc_client = SchemaRegistryUtils.get_schema_registry_client(SCHEMA_REGISTRY_URL)
  avro_schema_logs = SchemaRegistryUtils.get_avro_schema(sc_client, SCHEMA_REGISTRY_SUBJECT)

  spark.sql("DESCRIBE FORMATTED bronze_fast.all_topics").show()
  data_extracted = engine.extract_data(avro_schema_logs)
  data_transformed = engine.transform_data(data_extracted)
  query = engine.load_data_to_bronze(data_transformed)
  #query = engine.load_data_to_console(data_transformed)
  query.awaitTermination()