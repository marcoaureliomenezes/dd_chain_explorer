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
        .select(
          col("timestamp").alias("kafka_timestamp"),
          from_avro(expr("substring(value, 6)"), avro_schema).alias("data")
        )
        .select("kafka_timestamp", "data.*")
    )
    return df_simple_transactions


  def transform_data(self, df_stream):
    df_transformed = (
      df_stream
        .select("kafka_timestamp", "timestamp", "message")
        .filter(col("message").startswith("API_request"))
        .withColumn("api_key", split(col("message"), ";").getItem(1))
        .select("kafka_timestamp", "timestamp", "api_key")
    )


    window_1D = window(col("kafka_timestamp"), "1 day")
    df_windowed = (
      df_transformed
        .withWatermark("kafka_timestamp", "1 day")
        .groupBy(col("api_key"), window_1D)
        .agg(count("*").alias("count"), max("kafka_timestamp").alias("max_timestamp"))
        .select(
          col("api_key").alias("name").cast(StringType()), 
          col("window.start").alias("start").cast(StringType()), 
          col("window.end").alias("end").cast(StringType()), 
          col("count").alias("num_req_1d").cast(IntegerType()),
          col("max_timestamp").alias("last_req").cast(StringType())
        )
    )
    return df_windowed


  def load_data_to_console(self, df_transformed):
    write_stream_query = (
      df_transformed
        .writeStream
        .outputMode("complete")
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



if __name__ == "__main__":
    
  APP_NAME = "Handle_Simple_Transactions"
  SPARK_URL = os.getenv("SPARK_MASTER_URL")

  KAFKA_CLUSTER = os.getenv("KAFKA_BROKERS")
  TOPIC_SUBSCRIBE = os.getenv("TOPIC_LOGS")
  CONSUMER_GROUP = os.getenv("CG_API_KEY_CONSUME")
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
    "subscribe": TOPIC_SUBSCRIBE,
    "startingOffsets": STARTING_OFFSETS,
    "group.id": CONSUMER_GROUP,
    "maxOffsetsPerTrigger": MAX_OFFSETS_PER_TRIGGER 
  }

  engine = APIKeyMonitor(spark, kafka_options, redis_client)
  sc_client = SchemaRegistryUtils.get_schema_registry_client(SCHEMA_REGISTRY_URL)
  avro_schema_logs = SchemaRegistryUtils.get_avro_schema(sc_client, SCHEMA_REGISTRY_SUBJECT)

  data_extracted = engine.extract_data(avro_schema_logs)
  data_transformed = engine.transform_data(data_extracted)
  query = engine.load_data_to_redis(data_transformed)
  query.awaitTermination()