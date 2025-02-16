import os
import logging
from logging import Logger
from datetime import datetime as dt
import redis

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, lpad
from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler


class RawToBronzeBlocksEngine:

  def __init__(self, logger: Logger, spark: SparkSession):
    self.logger = logger
    self.spark = spark
    self.df_batch = None


  def config_source(self, table_input):
    self.table_input = table_input
    self.logger.info(f"Reading data from {table_input}")
    return self


  def config_sink(self, redis_client):
    self.redis_client = redis_client
    self.logger.info(f"Redis client configured")
    return self


  def extract(self):
    self.df_batch = self.spark.table(self.table_input )
    self.logger.info(f"Data extracted")
    return self


  def transform(self):
    assert self.df_batch, "No data to transform."
    self.df_batch  = (
      self.df_batch
        .groupBy("to_address").count()
        .orderBy(col("count").desc())
        .limit(30))
    self.logger.info(f"Data transformed")
    return self


  def load(self):
    list_of_popular_contract_addresses = [{"address": row["to_address"], "count": row["count"]} for row in self.df_batch.collect()]
    for contract in list_of_popular_contract_addresses:
      self.redis_client.set(contract["address"], contract["count"])
    self.logger.info(f"Data loaded.")
    return


if __name__ == "__main__":
    
  APP_NAME = os.getenv("APP_NAME")
  TABLE_NAME = "nessie.silver.transactions_contracts"
  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  TABLE_NAME = os.getenv("TABLE_NAME")
  REDIS_DB = 3

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  
  redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, decode_responses=True, db=3)

  _ = (
    RawToBronzeBlocksEngine(LOGGER, spark)
      .config_source(TABLE_NAME)
      .config_sink(redis_client)
      .extract()
      .transform()
      .load()
  )


  


