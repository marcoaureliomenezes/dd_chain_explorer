import os
import logging

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, lpad
from spark_utils import get_spark_session
from logger_utils import ConsoleLoggingHandler, KafkaLoggingHandler


class RawToBronzeBlocksETL:


  def __init__(self, logger, spark, raw_data_path, bronze_table_name):
    self.logger = logger
    self.spark = spark
    self.bronze_table_name = bronze_table_name
    self.partition_level = "/*/*/*/*"
    self.raw_data_path = raw_data_path

  def extract(self):
    path = self.raw_data_path + self.partition_level
    df_blocks_raw = (
    self.spark.read.format("parquet")
      .option("basePath", self.raw_data_path)
      .load(path)
    )
    return df_blocks_raw


  def transform(self, df_raw):
    df_bronze = (
      df_raw
        .withColumn("month", lpad(col("month"), 2, '0'))
        .withColumn("day", lpad(col("day"), 2, '0'))
        .withColumn("dat_ref_carga", concat_ws("-", col("year"), col("month"), col("day")))
        .drop("year", "month", "day")
    )
    return df_bronze


  def load(self, df):
    df.write.format("parquet").mode("overwrite").save(self.bronze_table_path)


if __name__ == "__main__":
  

  APP_NAME = os.getenv("APP_NAME")
  BRONZE_TABLENAME = os.getenv("BRONZE_TABLENAME")
  PATH_RAW_DATA = os.getenv("PATH_RAW_DATA")
  DATA = '2024-07-28'
  HORA = '02'

  # Configurando Logging
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  ConsoleLoggingHandler = ConsoleLoggingHandler()
  LOGGER.addHandler(ConsoleLoggingHandler)

  spark = SparkSession.builder.appName(APP_NAME).getOrCreate()
  spark.sparkContext.setLogLevel("ERROR")

  etl_engine = RawToBronzeBlocksETL(LOGGER, spark, PATH_RAW_DATA, BRONZE_TABLENAME)
  df_raw = etl_engine.extract()
  df_bronze = etl_engine.transform(df_raw)
  df_bronze.show(20)
  df_bronze.printSchema()


  # df_result = etl_engine.transform(df)
  # df_result.show()

