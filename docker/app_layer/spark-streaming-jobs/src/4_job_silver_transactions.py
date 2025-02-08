import os
import os

from pyspark.sql.functions import col, expr, explode, array_size, to_timestamp
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *

from schema_registry_utils import SchemaRegistryUtils
from spark_utils import SparkUtils



class SilverBlocks:
   
  def __init__(self, spark):
    self.spark = spark

  def get_schema_input(self):
    return StructType([
      StructField('key', BinaryType(), True),
      StructField('value', BinaryType(), True),
      StructField('partition', IntegerType(), True),
      StructField('offset', LongType(), True),
      StructField('timestamp', TimestampType(), True),
      StructField('topic', StringType(), True)])
  

  def extract_data(self, bronze_src_tbl, topic):
    df_extracted = (
      self.spark
        .readStream
        .format("iceberg")
        .schema(self.get_schema_input())
        .option("maxFilesPerTrigger", 10)
        .load(bronze_src_tbl)
        .filter(col("topic").isin(topic))
        .select("key","value","partition","offset","timestamp","topic")
        )
    return df_extracted

    
  def transform_data(self, dataframe, schema):
    df_transformed = (
      dataframe
        .select(
          col("timestamp").alias("ingestion_timestamp"),
          from_avro(expr("substring(value, 6)"), schema).alias("data"))
        .select("ingestion_timestamp", "data.*")
        .drop("withdrawals")
        .withColumnRenamed("blockNumber", "block_number")
        .withColumnRenamed("transactionIndex", "transaction_index")
        .withColumnRenamed("gasPrice", "gas_price")
        .withColumnRenamed("from", "from_address")
        .withColumnRenamed("to", "to_address")
        .withColumn("dt_hour_ref", expr("date_format(ingestion_timestamp, 'yyyy-MM-dd-HH')"))
        .select("ingestion_timestamp", "block_number", "hash", "transaction_index", "from_address", "to_address", "value", "input", "gas", "gas_price", "nonce", "dt_hour_ref"))
    return df_transformed

    
  def load_data_to_console(self, df_transformed):
    df_transformed.printSchema()
    query = (
      df_transformed
        .writeStream
        .outputMode("append")
        .option("checkpointLocation", "s3a://spark/checkpoints/console/silver_blocks")
        .format("console")
        .start())
    return query



  def load_data_to_silver_txs(self, df_transformed, table_name, checkpoint_location):
    query = (
      df_transformed
        .writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_location)
        .toTable(table_name))
    return query
  

if __name__ == "__main__":

  APP_NAME = "Silver_Transactions"
  SR_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
  TOPIC_TXS = os.getenv("TOPIC_TXS")
  TABLE_BRONZE = os.getenv("TABLE_BRONZE")
  TABLE_SILVER_TXS = os.getenv("TABLE_SILVER_TXS")
  CHECKPOINT_TXS = "s3a://spark/checkpoints/iceberg/silver_transactions"

  sc_client = SchemaRegistryUtils.get_schema_registry_client(SR_URL)
  schema_txs = SchemaRegistryUtils.get_avro_schema(sc_client, f"{TOPIC_TXS}-value")
  spark = SparkUtils.get_spark_session(APP_NAME)
  
  engine = SilverBlocks(spark)
  data_extracted = engine.extract_data(TABLE_BRONZE, TOPIC_TXS)
  data_transformed = engine.transform_data(data_extracted, schema_txs)
  #stream = engine.load_data_to_console(data_transformed)
  stream = engine.load_data_to_silver_txs(data_transformed, TABLE_SILVER_TXS, CHECKPOINT_TXS)
  stream.awaitTermination()
