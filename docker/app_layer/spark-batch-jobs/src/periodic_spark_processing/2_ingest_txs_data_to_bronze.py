import os
import logging
from logging import Logger
from datetime import datetime as dt
import redis

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler


class RawToBronzePopularContracts:

  def __init__(self, logger: Logger, spark: SparkSession):
    self.logger = logger
    self.spark = spark
    self.df_batch = None


  def config_source(self, src_configs):
    self.date = src_configs["date"]
    full_path = f"s3a://{src_configs["bucket"]}/{src_configs["prefix"]}"
    full_path += f"/year={self.date.year}/month={self.date.month}/day={self.date.day}/hour={self.date.hour}/*"
    self.path_input = full_path
    self.logger.info(f"Reading data from {full_path}")
    return self


  def config_sink(self, table_output):
    self.table_output = table_output
    self.logger.info(f"Redis client configured")
    return self


  def extract(self):
    self.df_batch = spark.read.format("json").load(self.path_input)
    self.logger.info(f"Data extracted")
    return self


  def transform(self):
    self.df_batch = self.df_batch.withColumn("dat_ref_hour", lit(self.date.strftime("%Y-%m-%d %H:00:00")))
    return self


  def load(self):
    print(self.df_batch.count())
    self.df_batch.printSchema()
    self.df_batch.writeTo(self.table_output).partitionedBy("dat_ref_hour").append()
    return


if __name__ == "__main__":
    
  APP_NAME = os.getenv("APP_NAME")
  REDIS_DB = 3

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  BUCKET_RAW_DATA = "raw-data"
  BUCKET_PREFIX = "contracts_transactions"
  EXEC_DATE = os.getenv("EXEC_DATE")
  print(EXEC_DATE)
  exec_date = dt.strptime(EXEC_DATE, "%Y-%m-%d %H:%M:%S%z")
  print(exec_date)
  TABLE_BRONZE = "nessie.bronze.popular_contracts_txs"
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  
  src_configs = {"bucket": BUCKET_RAW_DATA, "prefix": BUCKET_PREFIX, "date": exec_date}
  
  _ = (
    RawToBronzePopularContracts(LOGGER, spark)
      .config_source(src_configs)
      .config_sink(TABLE_BRONZE)
      .extract()
      .transform()
      .load()
  )
    
    