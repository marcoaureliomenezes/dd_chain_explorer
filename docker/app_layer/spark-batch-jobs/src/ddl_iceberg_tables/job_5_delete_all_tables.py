import os
import logging

from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler
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
  tables_to_drop = [
    #"bronze.kafka_topics_multiplexed",
    #"bronze.popular_contracts_txs"
    "silver.mined_blocks_events",
    "silver.blocks",
    "silver.blocks_transactions",
    "silver.transactions_fast",
    "silver.app_logs_fast"
  ]

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)

  ddl_actor = TablesDestroyer(LOGGER, spark)
  ddl_actor.drop_tables(tables=tables_to_drop)




