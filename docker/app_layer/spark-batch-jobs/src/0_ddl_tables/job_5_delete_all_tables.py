import os
import logging

from utils.spark_utils import SparkUtils
from utils.logger_utils import ConsoleLoggingHandler
from typing import List

class TablesDestroyer:

  def __init__(self, logger, spark):
    self.logger = logger
    self.spark = spark
     

  def drop_tables(self, tables: List[str], purge: bool = False):
    purge_data = "PURGE" if purge else ""
    for table in tables:
      self.spark.sql(f"DROP TABLE IF EXISTS {table} {purge_data}").show()
      self.logger.info(f"Table {table} dropped successfully!")
    return


if __name__ == "__main__":

  APP_NAME = "Delete_All_Tables"
  spark = SparkUtils.get_spark_session(APP_NAME)
  tables_to_drop = [
    "nessie.silver.blocks_transactions",
    "nessie.silver.transactions",
    "nessie.silver.blocks",
    "nessie.bronze.kafka_topics_multiplexed"
  ]

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  ddl_actor = TablesDestroyer(LOGGER, spark)
  ddl_actor.drop_tables(tables=tables_to_drop)




