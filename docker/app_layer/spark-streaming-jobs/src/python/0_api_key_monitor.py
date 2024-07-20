# Exemplo em Python (PySpark)
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, split, count, window, max
from pyspark.sql.types import StructType, StringType, IntegerType
from random import randint
import os



def main(spark, kafka_options, scylla_options):
  df_logs = (
    spark
      .readStream
      .format("kafka")
      .options(**kafka_options)
      .load()
      .select(col("timestamp"), col("value").cast(StringType()))
      .filter(col("value").startswith("API_request"))
      .withColumn("api_key", split(col("value"), ";").getItem(1))
      .select(col("timestamp"), col("api_key"))
  )

  window_1D = window(col("timestamp"), "1 day")
  df_windowed_counts = (
    df_logs
      .withWatermark("timestamp", "1 day")
      .groupBy(col("api_key"), window_1D)
      .agg(count("*").alias("count"), max("timestamp").alias("max_timestamp"))
      .select(
        col("api_key").alias("name").cast(StringType()), 
        col("window.start").alias("start").cast(StringType()), 
        col("window.end").alias("end").cast(StringType()), 
        col("count").alias("num_req_1d").cast(IntegerType()),
        col("max_timestamp").alias("last_req").cast(StringType())
      )
  )

  return (
    df_windowed_counts.writeStream
      .format("org.apache.spark.sql.cassandra")
      .option("checkpointLocation", "/tmp/dm_checkpoint")
      .outputMode("update")
      .trigger(processingTime="1 seconds")
      .foreachBatch(lambda df, epoch_id: 
        df.write.mode("append")
          .format("org.apache.spark.sql.cassandra")
          .options(**scylla_options).save()
      )
      .start()  
  )

def get_spark_session():
  spark = (
    SparkSession
      .builder
      .appName(APP_NAME)
      .master(SPARK_URL)
      .getOrCreate()
  )

  spark.sparkContext.setLogLevel("ERROR")
  return spark

if __name__ == "__main__":

  SPARK_URL = os.getenv("SPARK_MASTER_URL")
  KAFKA_CLUSTER = os.getenv("KAFKA_BROKERS")
  TOPIC_SUBSCRIBE = os.getenv("TOPIC_SUBSCRIBE")
  CONSUMER_GROUP = os.getenv("CONSUMER_GROUP")
  SCYLLA_HOST = os.getenv("SCYLLA_HOST")
  SCYLLA_PORT = os.getenv("SCYLLA_PORT")
  SCYLLA_KEYSPACE = os.getenv("SCYLLA_KEYSPACE")
  SCYLLA_TABLE = os.getenv("SCYLLA_TABLE")
  APP_NAME = "Handle_Simple_Transactions"
  STARTING_OFFSETS = os.getenv("STARTING_OFFSETS")
  MAX_OFFSETS_PER_TRIGGER = os.getenv("MAX_OFFSETS_PER_TRIGGER")


  spark = get_spark_session()

  kafka_options = {
    "kafka.bootstrap.servers": KAFKA_CLUSTER,
    "subscribe": TOPIC_SUBSCRIBE,
    "startingOffsets": STARTING_OFFSETS,
    "group.id": CONSUMER_GROUP,
    "maxOffsetsPerTrigger": MAX_OFFSETS_PER_TRIGGER,
    
  }

  scylla_options = {
    "spark.cassandra.connection.host": SCYLLA_HOST,
    "spark.cassandra.connection.port": SCYLLA_PORT,
    "keyspace": SCYLLA_KEYSPACE,
    "table": SCYLLA_TABLE
  }

  streaming_query = main(spark, kafka_options, scylla_options)
  streaming_query.awaitTermination()