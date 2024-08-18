




from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, concat_ws, lpad
from pyspark.sql.types import StructType, StringType, IntegerType, StructField, LongType, ArrayType
import os





def spark_session_with_hive(app_name: str, master_url: str) -> SparkSession:
  spark = (
    SparkSession.builder
      .appName(app_name)
      .master(master_url)
      .config("spark.sql.warehouse.dir", "hdfs://namenode:9000/user/hive/warehouse")
      .config("hive.metastore.uris", "thrift://hive-metastore:9083")
      .enableHiveSupport()
      .getOrCreate()
  )
  spark.sparkContext.setLogLevel("ERROR")
  return spark
  

def spark_session_with_iceberg(app_name: str, master_url: str) -> SparkSession:
  spark = (
    SparkSession.builder
    .appName(app_name)
    .master(master_url)
    .getOrCreate()
  )
  spark.sparkContext.setLogLevel("ERROR")
  return spark


def get_spark_session(app_name: str, master_url: str) -> SparkSession:
    spark = SparkSession.builder.appName(app_name).master(master_url).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


if __name__ == "__main__":
    

  SPARK_URL = "spark://spark-master:7077"
  RAW_TO_BRONZE_BLOCKS = "Batch_Simple_Transactions"
  BRONZE_TABLE_NAME = "bronze_blocks"
  PATH_BLOCKS_RAW = "hdfs://namenode:9000/raw/application_logs/mainnet.application.logs"


  spark = spark_session_with_iceberg(RAW_TO_BRONZE_BLOCKS, SPARK_URL)
  spark.sql("SHOW CATALOGS").show()
  spark.sql("SHOW DATABASES").show()

  def create_table_blocks(spark):
    spark.sql("CREATE DATABASE IF NOT EXISTS b_blocks")
    spark.sql("DROP TABLE IF EXISTS b_blocks.bronze_blocks")

    field_withdrawals = StructType([
      StructField("index", LongType(), True),
      StructField("validatorIndex", LongType(), True),
      StructField("address", StringType(), True),
      StructField("amount", LongType(), True),
    ])


    schema = StructType([
      StructField("number", LongType(), True),
      StructField("timestamp", LongType(), True),
      StructField("hash", LongType(), True),
      StructField("parentHash", StringType(), True),
      StructField("difficulty", StringType(), True),
      StructField("totalDifficulty", StringType(), True),
      StructField("nonce", LongType(), True),
      StructField("size", LongType(), True),
      StructField("miner", LongType(), True),
      StructField("baseFeePerGas", StringType(), True),
      StructField("gasLimit", StringType(), True),
      StructField("gasUsed", StringType(), True),
      StructField("logsBloom", StringType(), True),
      StructField("extraData", StringType(), True),
      StructField("transactionsRoot", StringType(), True),
      StructField("transactions", ArrayType(StringType()), True),
      StructField("withdrawals", ArrayType(field_withdrawals), True),
      StructField("dat_ref_carga", StringType(), True)
    ])

    spark.createDataFrame([], schema=schema).write.format('iceberg').mode("overwrite").partitionBy("dat_ref_carga").saveAsTable("iceberg_db.bronze_blocks")



  spark.sql("CREATE DATABASE IF NOT EXISTS iceberg_db")
  spark.sql("CREATE TABLE IF NOT EXISTS iceberg_db.b_logs (id INT, name STRING, age INT) USING iceberg")

  
  create_table_blocks(spark)



