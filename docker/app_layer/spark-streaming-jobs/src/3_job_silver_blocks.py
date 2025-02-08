import os

from pyspark.sql.functions import col, expr, explode, array_size, to_timestamp
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *

from schema_registry_utils import SchemaRegistryUtils
from spark_utils import SparkUtils



class SilverBlocks:
   
  def __init__(self, spark, silver_blocks, silver_blocks_txs):
    self.spark = spark
    self.silver_blocks = silver_blocks
    self.silver_blocks_txs = silver_blocks_txs

  def get_schema_input(self):
    return StructType([
      StructField('key', BinaryType(), True),
      StructField('value', BinaryType(), True),
      StructField('partition', IntegerType(), True),
      StructField('offset', LongType(), True),
      StructField('timestamp', TimestampType(), True),
      StructField('topic', StringType(), True),
      StructField('ohour', StringType(), True)])

  def extract_data(self, bronze_src_tbl, topic):
    df_extracted = (
      self.spark
        .readStream
        .format("iceberg")
        .schema(self.get_schema_input())
        .option("maxFilesPerTrigger", 4)
        .load(bronze_src_tbl)
        .filter(col("topic").isin(topic))
        .select("key","value","partition","offset","timestamp","topic", "ohour")
        )
    return df_extracted

    
  def transform_data(self, df_extracted, schema):
    df_transformed = (
        df_extracted
        .select(col("timestamp").alias("ingestion_timestamp"), from_avro(expr("substring(value, 6)"), schema).alias("data"))
        .select("ingestion_timestamp", "data.*").drop("withdrawals")
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
        .withColumn("dt_hour_ref", expr("date_format(block_timestamp, 'yyyy-MM-dd-HH')")))
    return df_transformed

    

  def load_data_to_console(self, df_transformed):
    # final_columns = ["timestamp", "block_number", "transaction_id"]
    # df_to_write = (
    #   df_transformed
    #   .withColumn("transaction_id", explode(col("transactions")))
    #   .withColumn("block_number", col("number"))
    #   .select(*final_columns))
    query = (
      df_transformed
        .writeStream
        .outputMode("append")
        .option("checkpointLocation", "s3a://spark/checkpoints/console/silver_blocks")
        .format("console")
        .trigger(processingTime="10 seconds")
        .start())
    return query


  def __prepare_silver_blocks(self, df_transformed):
    final_columns = [
      "ingestion_timestamp", "block_timestamp", "number", "hash", "parent_hash", "difficulty", "total_difficulty", "nonce", 
      "size", "miner", "base_fee_per_gas", "gas_limit", "gas_used", "logs_bloom", "extra_data", 
      "transactions_root", "state_root", "num_transactions", "dt_hour_ref"]
    df_to_write = (
      df_transformed
        .withColumn("num_transactions", array_size(col("transactions")))
        .select(*final_columns))
    return df_to_write
  

  def __prepare_silver_blocks_txs(self, df_transformed):
    final_columns = ["block_timestamp", "block_number", "transaction_id", "dt_hour_ref"]
    df_to_write = (
      df_transformed
      .withColumn("transaction_id", explode(col("transactions")))
      .withColumn("block_number", col("number"))
      .select(*final_columns))
    return df_to_write
  

  def _microbatch_write(self, df, epoch_id):
    df_silver_blocks = self.__prepare_silver_blocks(df)
    df_silver_blocks_txs = self.__prepare_silver_blocks_txs(df)
    df_silver_blocks.writeTo(self.silver_blocks).append()
    df_silver_blocks_txs.writeTo(self.silver_blocks_txs).append()


  def load_data_to_silver_blocks(self, df_transformed, checkpoint_location):
    query = (
      df_transformed
        .writeStream
        .foreachBatch(self._microbatch_write)
        .outputMode("append")
        .option("checkpointLocation", checkpoint_location)
        .trigger(processingTime="10 seconds")
        .start())
    return query
  


if __name__ == "__main__":

  APP_NAME = "Silver_Blocks"
  SR_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
  TOPIC_BLOCKS = os.getenv("TOPIC_BLOCKS")
  TABLE_BRONZE = os.getenv("TABLE_BRONZE")
  TABLE_SILVER_BLOCKS = os.getenv("TABLE_SILVER_BLOCKS")
  TABLE_SILVER_BLOCKS_TXS = os.getenv("TABLE_SILVER_BLOCKS_TXS")
  PATH_CHECKPOINT_CONSOLE = "s3a://spark/checkpoints/console/silver_blocks"
  PATH_CHECKPOINT_ICEBERG = "s3a://spark/checkpoints/iceberg/silver_blocks"

  sc_client = SchemaRegistryUtils.get_schema_registry_client(SR_URL)
  schema_blocks = SchemaRegistryUtils.get_avro_schema(sc_client, f"{TOPIC_BLOCKS}-value")
  spark = SparkUtils.get_spark_session(APP_NAME)


  engine = SilverBlocks(spark, TABLE_SILVER_BLOCKS, TABLE_SILVER_BLOCKS_TXS)
  data_extracted = engine.extract_data(TABLE_BRONZE, TOPIC_BLOCKS)
  data_transformed = engine.transform_data(data_extracted, schema_blocks)
  stream = engine.load_data_to_silver_blocks(data_transformed, PATH_CHECKPOINT_ICEBERG)
  #stream = engine.load_data_to_console(data_transformed)
  stream.awaitTermination()

