import os
import logging

from utils.spark_utils import SparkUtils
from utils.logger_utils import ConsoleLoggingHandler
from table_creator import TableCreator


class DDLBronzeTables:

  def __init__(self, logger):
    self.logger = logger

  def build_create_table_query_bronze_multiplexed(self, table_name, tbl_properties):
    query = f"""
      CREATE TABLE IF NOT EXISTS {table_name} (
        key BINARY                    COMMENT 'Key',
        value BINARY                  COMMENT 'Kafka Value Binary',   
        partition INT                 COMMENT 'Kafka Message Partition',
        offset LONG                   COMMENT 'Kafka Message Offset',
        ingestion_time TIMESTAMP      COMMENT 'Kafka Message Timestamp',
        topic STRING                  COMMENT 'Partition Field Kafka Topic',
        dat_ref STRING                COMMENT 'Partition Field with Date')
      USING ICEBERG 
      PARTITIONED BY (dat_ref, topic)
      """
    query += tbl_properties
    return query



  def build_create_table_query_bronze_txs(self, table_name, tbl_properties):
    query = f"""
      CREATE TABLE IF NOT EXISTS {table_name} (
        blockHash STRING                    COMMENT 'Block Hash',
        blockNumber STRING                  COMMENT 'Block Number',
        confirmations STRING                COMMENT 'Confirmations',
        contractAddress STRING              COMMENT 'Contract Address',
        cumulativeGasUsed STRING            COMMENT 'Cumulative Gas Used',
        from STRING                         COMMENT 'From',
        functionName STRING                 COMMENT 'Function Name',
        gas STRING                          COMMENT 'Gas',
        gasPrice STRING                     COMMENT 'Gas Price',
        gasUsed STRING                      COMMENT 'Gas Used',
        hash STRING                         COMMENT 'Hash',
        input STRING                        COMMENT 'Input',
        isError STRING                      COMMENT 'Is Error',
        methodId STRING                     COMMENT 'Method Id',
        nonce STRING                        COMMENT 'Nonce',
        timeStamp STRING                    COMMENT 'Time Stamp',
        to STRING                           COMMENT 'To',
        transactionIndex STRING             COMMENT 'Transaction Index',
        txreceipt_status STRING             COMMENT 'Txreceipt Status',
        value STRING                        COMMENT 'Value',
        dat_ref_hour STRING                 COMMENT 'Partition Field with Date'
      )
      USING ICEBERG
      PARTITIONED BY (dat_ref_hour)
      """
    query += tbl_properties
    return query
  



if __name__ == "__main__":

  APP_NAME = "Create_Bronze_tables"
  table_bronze_kafka_multiplexed = "nessie.bronze.kafka_topics_multiplexed"
  table_bronze_transactions_batch = "nessie.bronze.popular_contracts_txs"

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  tables_creator = TableCreator(LOGGER, spark)
  tables_creator.create_namespace("nessie.bronze")
  
  table_properties = tables_creator.get_iceberg_table_properties()
  ddl_actor = DDLBronzeTables(LOGGER)
  ddl_query = ddl_actor.build_create_table_query_bronze_txs(table_bronze_transactions_batch, table_properties)
  spark.sql(ddl_query)
  tables_creator.get_table_info(table_bronze_transactions_batch)

  ddl_query = ddl_actor.build_create_table_query_bronze_multiplexed(table_bronze_kafka_multiplexed, table_properties)
  spark.sql(ddl_query)
  tables_creator.get_table_info(table_bronze_kafka_multiplexed)
