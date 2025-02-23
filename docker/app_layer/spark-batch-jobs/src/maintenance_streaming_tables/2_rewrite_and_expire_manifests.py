import os
import logging
from datetime import datetime as dt

from iceberg_maintenance import IceStreamMaintainer
from dm_33_utils.logger_utils import ConsoleLoggingHandler
from utils.spark_utils import SparkUtils


def get_logger(app_name):
  logger = logging.getLogger(app_name)
  logger.setLevel(logging.INFO)
  logger.addHandler(ConsoleLoggingHandler())
  return logger

if __name__ == "__main__":

  TABLE_NAME = os.getenv("TABLE_FULLNAME")
  HOURS_RETAIN = int(os.getenv("HOURS_RETAIN"))
  MIN_SNAPSHOTS = int(os.getenv("MIN_SNAPSHOTS"))
  APP_NAME = f"PERIODIC_MAINTENANCE_REWRITE_EXPIRE_MANIFESTS_{TABLE_NAME.upper()}"
  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  maintainer = IceStreamMaintainer(LOGGER, spark, table=TABLE_NAME)
  maintainer.expire_snapshots(hours_retained=24, min_snapshots_to_retain=5)