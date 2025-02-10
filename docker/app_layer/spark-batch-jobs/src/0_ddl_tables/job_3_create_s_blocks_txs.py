import os
import logging

from utils.spark_utils import SparkUtils
from utils.logger_utils import ConsoleLoggingHandler
from table_creator import TableCreator


class CreateIcebergSilverBlocksTxs(TableCreator):

  def create_table(self):
    self.create_namespace()
    query = f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
      block_timestamp TIMESTAMP           COMMENT 'Block timestamp',
      ingestion_time TIMESTAMP            COMMENT 'Kafka ingestion_time',
      block_number LONG                   COMMENT 'Block number',
      transaction_id STRING               COMMENT 'Number of transactions',
      dat_ref STRING                      COMMENT 'Partition Field with Date of Kafka Message')
    USING ICEBERG
    PARTITIONED BY (dat_ref)"""
    query += self.get_iceberg_table_properties()
    self.spark.sql(query).show()
    print(f"Table {self.table_name} created successfully!")
    self.table_exists = True
    return self


if __name__ == "__main__":

  APP_NAME = "Create_Table_Silver_Blocks_Transactions"
  TABLE_NAME = os.getenv("TABLE_FULLNAME")

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  ddl_actor = CreateIcebergSilverBlocksTxs(spark, table_name=TABLE_NAME)
  ddl_actor.create_table()
  ddl_actor.get_table_info()



