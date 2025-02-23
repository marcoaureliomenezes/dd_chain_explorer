import os
import logging

from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler
from table_creator import TableCreator


class CreateIcebergSilverLogs:


  def create_table_logs(self, table_name, tbl_properties):
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
      log_timestamp TIMESTAMP             COMMENT 'Timestamp of the log',
      ingestion_time TIMESTAMP            COMMENT 'Ingestion timestamp',
      logger STRING                       COMMENT 'Logger name',
      level STRING                        COMMENT 'Log level',
      filename STRING                     COMMENT 'Filename',
      function_name STRING                COMMENT 'Function name',
      message STRING                      COMMENT 'Log message',
      dat_ref STRING                      COMMENT 'Reference date')
    USING ICEBERG
    PARTITIONED BY (dat_ref)"""
    query += tbl_properties
    return query


if __name__ == "__main__":

  APP_NAME = "CREATE_SILVER_FAST_LOGS_TABLES"
  TABLE_SILVER_APP_LOGS = "s_logs.apps_logs_fast"

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  tables_creator = TableCreator(LOGGER, spark)
  tbl_properties = tables_creator.get_iceberg_table_properties()
  tables_creator.create_namespace("s_logs")


  ddl_actor = CreateIcebergSilverLogs()
  query = ddl_actor.create_table_logs(TABLE_SILVER_APP_LOGS, tbl_properties)
  spark.sql(query)
  tables_creator.get_table_info(TABLE_SILVER_APP_LOGS)




