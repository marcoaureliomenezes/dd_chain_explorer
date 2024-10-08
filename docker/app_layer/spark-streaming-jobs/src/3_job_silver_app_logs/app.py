import os
from utils.spark import get_spark_session
import os

from pyspark.sql.functions import col, expr
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import *

from utils.schema_registry_utils import SchemaRegistryUtils


class SilverBlocks:
   
  def __init__(self, spark, silver_tbl_name):
    self.spark = spark
    self.silver_tbl_name = silver_tbl_name


  def create_table(self):
    self.spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {self.silver_tbl_name} (
    key binary,
    value binary,
    partition int,
    offset long,
    timestamp timestamp,
    topic string) 
    USING ICEBERG PARTITIONED BY (topic)
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
    df_extracted = (
      self.spark
        .readStream
        .format("iceberg")
        .schema(schema)
        .table(bronze_src_tbl)
        .filter(col("topic") == "mainnet.mined.txs.token.transfer")
        .select("key","value","partition","offset","timestamp","topic"))
    return df_extracted

    
  def transform_data(self, df_extracted):   
    df_transformed = (
        df_blocks
        .select(
          col("timestamp").alias("kafka_timestamp"),
          from_avro(expr("substring(value, 6)"), schema_blocks).alias("data"))
        .select("kafka_timestamp", "data.*")
    )
    return df_transformed

    
  def load_data_to_console(self, df_transformed):
    query = (
      df_transformed
        .writeStream
        .outputMode("append")
        .format("console")
        .start())
    return query

  def load_data_to_bronze(self, df_transformed):
    query = (
      df_transformed
        .writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", "s3a://sistemas/checkpoints/silver")
        .toTable(self.silver_tbl_name))
    return query


os.environ["SPARK_MASTER_URL"] = "spark://spark-master:7077"
SCHEMA_REGISTRY_URL = "http://schema-registry:8081"
sc_client = SchemaRegistryUtils.get_schema_registry_client(SCHEMA_REGISTRY_URL)
topic_blocks = "mainnet.mined.block.metadata-value"
schema_blocks = SchemaRegistryUtils.get_avro_schema(sc_client, topic_blocks)
print(schema_blocks)

spark = get_spark_session("silver_blocks")

silver_blocks = 'nessie.blocks'
bronze_src_tbl = "nessie.test"
print(spark.table(bronze_src_tbl).schema)
spark.table(silver_blocks).show()


