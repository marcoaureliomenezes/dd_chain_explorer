import os
import os

from pyspark.sql.functions import col, expr, explode, array_size, to_timestamp
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *

from schema_registry_utils import SchemaRegistryUtils
from spark_utils import SparkUtils


class LakeDDLActor:

  def __init__(self, spark):
    self.spark = spark

  def create_table_txs(self, table_name):
    self.spark.sql("CREATE NAMESPACE IF NOT EXISTS nessie.silver")
    self.spark.sql(f"""
    CREATE OR REPLACE TABLE {table_name} (
    kafka_timestamp TIMESTAMP         COMMENT 'Kafka timestamp',  
    block_number LONG                 COMMENT 'Block number',
    hash STRING                       COMMENT 'Block hash',   
    transaction_index LONG            COMMENT 'Transaction index',      
    from_address STRING               COMMENT 'From address',
    to_address STRING                 COMMENT 'To address',
    value STRING                      COMMENT 'Value',
    input STRING                      COMMENT 'Input',
    gas LONG                          COMMENT 'Gas',
    gas_price LONG                    COMMENT 'Gas price',
    nonce LONG                        COMMENT 'Nonce'
    )
    USING ICEBERG
    PARTITIONED BY (hour(kafka_timestamp))
    TBLPROPERTIES ('gc.enabled' = 'true')""")
    self.spark.table(table_name).printSchema()


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
          col("timestamp").alias("kafka_timestamp"),
          from_avro(expr("substring(value, 6)"), schema).alias("data"))
        .select("kafka_timestamp", "data.*")
        .drop("withdrawals")
        .withColumnRenamed("blockNumber", "block_number")
        .withColumnRenamed("transactionIndex", "transaction_index")
        .withColumnRenamed("gasPrice", "gas_price")
        .withColumnRenamed("from", "from_address")
        .withColumnRenamed("to", "to_address")
        .select("kafka_timestamp", "block_number", "hash", "transaction_index", "from_address", "to_address", "value", "input", "gas", "gas_price", "nonce"))
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
  TOPIC_TXS = "mainnet.4.mined.txs.raw_data"
  BRONZE_MLTPLX = "nessie.bronze.data_multiplexed"
  CHECKPOINT_TXS = "s3a://spark/checkpoints/iceberg/silver_transactions"
  SILVER_TRANSACTIONS = 'nessie.silver.transactions'

  sc_client = SchemaRegistryUtils.get_schema_registry_client(SR_URL)
  schema_txs = SchemaRegistryUtils.get_avro_schema(sc_client, f"{TOPIC_TXS}-value")
  spark = SparkUtils.get_spark_session(APP_NAME)
  

  # ddl_actor = LakeDDLActor(spark)
  # ddl_actor.create_table_txs(SILVER_TRANSACTIONS)

  engine = SilverBlocks(spark)
  data_extracted = engine.extract_data(BRONZE_MLTPLX, TOPIC_TXS)
  data_transformed = engine.transform_data(data_extracted, schema_txs)
  #stream = engine.load_data_to_console(data_transformed)
  stream = engine.load_data_to_silver_txs(data_transformed, SILVER_TRANSACTIONS, CHECKPOINT_TXS)
  stream.awaitTermination()

