import os
import os

from pyspark.sql.functions import col, expr
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *

from schema_registry_utils import SchemaRegistryUtils
from spark_utils import SparkUtils


class SilverBlocks:
   
  def __init__(self, spark, silver_tbl_name):
    self.spark = spark
    self.silver_tbl_name = silver_tbl_name


  def create_table(self):
    self.spark.sql("CREATE NAMESPACE IF NOT EXISTS nessie.silver")
    self.spark.sql(f"""
    CREATE OR REPLACE TABLE {self.silver_tbl_name} (
    kafka_timestamp timestamp,
    number long,
    timestamp long,
    hash string,
    parent_hash string,
    difficulty long,
    total_difficulty string,
    nonce string,
    size long,
    miner string,
    base_fee_per_gas long,
    gas_limit long,
    gas_used long,
    logs_bloom string,
    extra_data string,
    transactions_root string,
    state_root string,
    transactions array<string>
    ) 
    USING ICEBERG
    PARTITIONED BY (hour(kafka_timestamp))
    """).show()
    spark.table(self.silver_tbl_name).printSchema()
    

  def extract_data(self, bronze_src_tbl):
    schema = StructType([
        StructField('key', BinaryType(), True),
        StructField('value', BinaryType(), True),
        StructField('partition', IntegerType(), True),
        StructField('offset', LongType(), True),
        StructField('timestamp', TimestampType(), True),
        StructField('topic', StringType(), True)]
    )
    spark.table(bronze_src_tbl).printSchema()
    #spark.sql("""CALL nessie.system.rewrite_data_files(table => 'bronze.data_multiplexed', where => 'topic = "mainnet.0.application.logs"')""")
    #spark.sql("""CALL nessie.system.expire_snapshots(table => 'bronze.data_multiplexed', retain_last => 3)""")
    print(bronze_src_tbl)
    df_extracted = (
      self.spark
        .readStream
        .format("iceberg")
        .schema(schema)
        .option("maxFilesPerTrigger", 10)
        .load(bronze_src_tbl)
        .filter(col("topic").isin("mainnet.1.mined_blocks.data", "mainnet.2.orphan_blocks.data"))
        .select("key","value","partition","offset","timestamp","topic")
        )
    return df_extracted

    
  def transform_data(self, df_extracted):
    df_transformed = (
        df_extracted
        .select(
          col("timestamp").alias("kafka_timestamp"),
          from_avro(expr("substring(value, 6)"), schema_blocks).alias("data"))
        .select("kafka_timestamp", "data.*").drop("withdrawals")
        .withColumnRenamed("parentHash", "parent_hash")
        .withColumnRenamed("totalDifficulty", "total_difficulty")
        .withColumnRenamed("baseFeePerGas", "base_fee_per_gas")
        .withColumnRenamed("gasLimit", "gas_limit")
        .withColumnRenamed("gasUsed", "gas_used")
        .withColumnRenamed("logsBloom", "logs_bloom")
        .withColumnRenamed("extraData", "extra_data")
        .withColumnRenamed("transactionsRoot", "transactions_root")
        .withColumnRenamed("stateRoot", "state_root")
    )
    df_transformed.printSchema()
    return df_transformed

    
  def load_data_to_console(self, df_transformed):
    query = (
      df_transformed
        .writeStream
        .outputMode("append")
        #.option("checkpointLocation", "s3a://sistemas/checkpoints/silver_c")
        .format("console")
        .start())
    return query

  def load_data_to_bronze(self, df_transformed):
    query = (
      df_transformed
        .writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", "s3a://sistemas/checkpoints/silver_blocks")
        .trigger(processingTime="10 seconds")
        .toTable(self.silver_tbl_name))
    return query



if __name__ == "__main__":

  APP_NAME = "APP_NAME"
  kafka_cluster = os.getenv("KAFKA_BROKERS", "broker:29092")
  schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
  consumer_group = os.getenv("CONSUMER_GROUP", "cg_silver")
  starting_offsets = os.getenv("STARTING_OFFSETS", "latest")
  max_offsets_per_trigger = os.getenv("MAX_OFFSETS_PER_TRIGGER", 1000)

  sc_client = SchemaRegistryUtils.get_schema_registry_client(schema_registry_url)
  topic_blocks = "mainnet.mined.block.metadata-value"
  schema_blocks = SchemaRegistryUtils.get_avro_schema(sc_client, topic_blocks)
  print(schema_blocks)

  spark = SparkUtils.get_spark_session(APP_NAME)

  bronze_src_tbl = "nessie.bronze.data_multiplexed"
  silver_blocks = 'nessie.silver.blocks'
  
  engine = SilverBlocks(spark, silver_blocks)
  engine.create_table()

  data_extracted = engine.extract_data(bronze_src_tbl)
  data_transformed = engine.transform_data(data_extracted)
  query = engine.load_data_to_bronze(data_transformed)
  query.awaitTermination()


