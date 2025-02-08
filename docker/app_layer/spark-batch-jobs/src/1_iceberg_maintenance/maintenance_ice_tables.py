import os
import logging
from datetime import datetime as dt


from ice_stream_maintainer import IceStreamMaintainer
from spark_utils import SparkUtils
from logger_utils import ConsoleLoggingHandler


def get_logger(app_name):
  logger = logging.getLogger(app_name)
  logger.setLevel(logging.INFO)
  logger.addHandler(ConsoleLoggingHandler())
  return logger

if __name__ == "__main__":

  TABLE_NAME = os.getenv("TABLE_FULLNAME")
  APP_NAME = f"Iceberg_Maintenance_Streaming_Table_{TABLE_NAME}"
  LOGGER = get_logger(APP_NAME)
  spark = SparkUtils.get_spark_session(APP_NAME)
  maintainer = IceStreamMaintainer(LOGGER, spark, table=TABLE_NAME)
  maintainer.rewrite_manifests()
  maintainer.rewrite_position_delete_files()
  maintainer.rewrite_data_files()
  #maintainer.remove_orphan_files()
  maintainer.expire_snapshots()