import os
import logging

from utils.spark_utils import SparkUtils
from utils.logger_utils import ConsoleLoggingHandler
from table_creator import TableCreator


class DDLSilverTables:

  def __init__(self, logger):
    self.logger = logger


  def build_create_table_query_silver_blocks(self, table_name, tbl_properties):
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
      ingestion_time TIMESTAMP            COMMENT 'Kafka ingestion_time',
      block_timestamp TIMESTAMP           COMMENT 'Block timestamp',
      number LONG                         COMMENT 'Block number', 
      hash STRING                         COMMENT 'Block hash',
      parent_hash STRING                  COMMENT 'Parent hash',
      difficulty long                     COMMENT 'Block difficulty',
      total_difficulty STRING             COMMENT 'Total difficulty',
      nonce STRING                        COMMENT 'Block nonce',
      size LONG                           COMMENT 'Block size',
      miner STRING                        COMMENT 'Block miner',
      base_fee_per_gas LONG               COMMENT 'Base fee per gas',
      gas_limit LONG                      COMMENT 'Block gas limit',
      gas_used LONG                       COMMENT 'Block gas used',
      logs_bloom STRING                   COMMENT 'Logs bloom',
      extra_data STRING                   COMMENT 'Extra data',
      transactions_root STRING            COMMENT 'Transactions root',
      state_root STRING                   COMMENT 'State root',
      num_transactions INT                COMMENT 'Number of transactions',
      dat_ref STRING                      COMMENT 'Partition Field with Date based on block_timestamp') 
    USING ICEBERG
    PARTITIONED BY (dat_ref)"""
    query += tbl_properties
    return query


  def build_create_table_query_silver_blocks_txs(self, table_name, tbl_properties):
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
      block_timestamp TIMESTAMP           COMMENT 'Block timestamp',
      ingestion_time TIMESTAMP            COMMENT 'Kafka ingestion_time',
      block_number LONG                   COMMENT 'Block number',
      transaction_id STRING               COMMENT 'Number of transactions',
      dat_ref STRING                      COMMENT 'Partition Field with Date of Kafka Message')
    USING ICEBERG
    PARTITIONED BY (dat_ref)"""
    query += tbl_properties
    return query


if __name__ == "__main__":


  APP_NAME = "Create_Silver_tables"
  table_silver_blocks = "nessie.silver.blocks"
  table_silver_blocks_transactions= "nessie.silver.blocks_transactions"

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  tables_creator = TableCreator(LOGGER, spark)
  tables_creator.create_namespace("nessie.silver")
  
  table_properties = tables_creator.get_iceberg_table_properties()
  ddl_actor = DDLSilverTables(LOGGER)
  ddl_query = ddl_actor.build_create_table_query_silver_blocks(table_silver_blocks, table_properties)
  spark.sql(ddl_query)
  tables_creator.get_table_info(table_silver_blocks)

  ddl_query = ddl_actor.build_create_table_query_silver_blocks_txs(table_silver_blocks_transactions, table_properties)
  spark.sql(ddl_query)
  tables_creator.get_table_info(table_silver_blocks_transactions)
