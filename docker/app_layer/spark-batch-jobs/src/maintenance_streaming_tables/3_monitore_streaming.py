import os
import logging
from datetime import datetime as dt
import redis
from iceberg_maintenance import IceStreamMaintainer
from dm_33_utils.logger_utils import ConsoleLoggingHandler
from utils.spark_utils import SparkUtils


def get_logger(app_name):
  logger = logging.getLogger(app_name)
  logger.setLevel(logging.INFO)
  logger.addHandler(ConsoleLoggingHandler())
  return logger

if __name__ == "__main__":

  TABLE_NAME = os.getenv("TABLE_FULLNAME", "test")
  APP_NAME = f"PERIODIC_MAINTENANCE_REWRITE_EXPIRE_MANIFESTS_{TABLE_NAME.upper()}"
  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  TABLE_NAME = os.getenv("TABLE_NAME")
  REDIS_DB = 5
  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  
  redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASS)
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  df_latest_txs = spark.sql("SELECT * FROM g_bench.latest_data")
  columns = df_latest_txs.columns
  data = [row.asDict() for row in df_latest_txs.collect()][0]
  data = {k: dt.strftime(v, "%Y-%m-%d %H:%M:%S") for k, v in data.items()}
  print(data)
  for column in columns:
    redis_client.set(f"{column}", data[column])
  LOGGER.info("Data written to redis successfully")

