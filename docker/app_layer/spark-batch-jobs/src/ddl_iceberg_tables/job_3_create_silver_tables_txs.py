import os
import logging

from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler
from table_creator import TableCreator


class CreateIcebergSilverTxs:


  def create_table_transactions(self, table_name, tbl_properties):
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
      ingestion_time TIMESTAMP          COMMENT 'Kafka timestamp',  
      block_number LONG                 COMMENT 'Block number',
      hash STRING                       COMMENT 'Block hash',
      transaction_type STRING           COMMENT 'Transaction type can be P2P, CONTRACT_CALL or CONTRACT_CREATION',  
      transaction_index LONG            COMMENT 'Transaction index',      
      from_address STRING               COMMENT 'From address',
      to_address STRING                 COMMENT 'To address',
      value STRING                      COMMENT 'Value',
      input STRING                      COMMENT 'Input',
      gas LONG                          COMMENT 'Gas',
      gas_price LONG                    COMMENT 'Gas price',
      nonce LONG                        COMMENT 'Nonce',
      dat_ref STRING                    COMMENT 'Partition Field with Date based on block_timestamp') 
    USING ICEBERG
    PARTITIONED BY (dat_ref)"""
    query += tbl_properties
    return query


if __name__ == "__main__":

  APP_NAME = "Create_Tables_Silver_Transactions"
  TABLE_SILVER_TXS_FAST = "silver.transactions_fast"

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  tables_creator = TableCreator(LOGGER, spark)
  tbl_properties = tables_creator.get_iceberg_table_properties()
  tables_creator.create_namespace("silver")

  ddl_actor = CreateIcebergSilverTxs()
  query = ddl_actor.create_table_transactions(TABLE_SILVER_TXS_FAST, tbl_properties)
  spark.sql(query)
  tables_creator.get_table_info(TABLE_SILVER_TXS_FAST)




