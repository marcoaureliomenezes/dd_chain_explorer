import os
from datetime import datetime as dt

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, lpad
from spark_utils import get_spark_session
from logger_utils import ConsoleLoggingHandler, KafkaLoggingHandler


class RawToBronzeBlocksEngine:

  def __init__(self, spark: SparkSession, raw_data_path, bronze_table_name: str):
    self.spark = spark
    self.bronze_table_name = f"{bronze_table_name}"
    self.raw_data_path = raw_data_path


  def configure_path(self, execution_datetime):
    partition_level = "/year=<year>/month=<month>/day=<day>/hour=<hour>"
    partition_level = partition_level.replace("<year>", str(execution_datetime.year))
    partition_level = partition_level.replace("<month>", str(execution_datetime.month))
    partition_level = partition_level.replace("<day>", str(execution_datetime.day))
    partition_level = partition_level.replace("<hour>", str(execution_datetime.hour))
    total_path = f"{self.raw_data_path}{partition_level}"
    return total_path


  def extract(self, execution_datetime):
    total_path = self.configure_path(execution_datetime)
    df_app_logs_raw = (
    self.spark.read.format("parquet")
      .option("basePath", self.raw_data_path)
      .load(total_path)
    )
    return df_app_logs_raw


  def transform(self, df_extracted):
    df_transformed = (
      df_extracted
      .withColumn("dat_ref_carga", concat_ws("-", col("year"), lpad(col("month"), 2, '0'), lpad(col("day"), 2, '0')))
    )
    return df_transformed


  def load(self, df):
    df.write.format("iceberg").mode("overwrite").partitionBy("dat_ref_carga").saveAsTable(self.bronze_table_name)



if __name__ == "__main__":
    
  APP_NAME = os.getenv("APP_NAME")
  BRONZE_TABLENAME = os.getenv("BRONZE_TABLENAME")
  PATH_RAW_DATA = os.getenv("PATH_RAW_DATA")


  odatetime = os.getenv("ODATETIME")

  # format = "2024-07-20 03:00:00+00:00"
  
  execution_datetime = dt.strptime(odatetime, '%Y-%m-%d %H:%M:%S%z')


  spark = SparkSession.builder.appName(APP_NAME).getOrCreate()
  spark.sparkContext.setLogLevel("ERROR")


  etl_engine = RawToBronzeBlocksEngine(spark, PATH_RAW_DATA, BRONZE_TABLENAME)
  df_app_logs_raw = etl_engine.extract(execution_datetime)
  df_app_logs_bronze = etl_engine.transform(df_app_logs_raw)

  df_app_logs_bronze.show()
  df_app_logs_bronze.printSchema()
  #_ = etl_engine.load(df_app_logs_bronze)
  
  spark.sql("SHOW DATABASES").show()
  #spark.table(f"iceberg_catalog.{BRONZE_TABLE_NAME}").show()
  # See partitions of the table with pySpark withouth using SQL
  #spark.sql("SELECT * FROM iceberg_catalog.b_app_logs.txs_crawler_logs2.partitions").show()


  


