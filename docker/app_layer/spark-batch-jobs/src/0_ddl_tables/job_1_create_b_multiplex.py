import os
import logging

from utils.spark_utils import SparkUtils
from utils.logger_utils import ConsoleLoggingHandler
from table_creator import TableCreator


class CreateIcebergBronzeTables(TableCreator):

  def build_create_table_query_bronze_multiplexed(self, table_name):
    self.create_namespace(table_name)
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
    query += self.get_iceberg_table_properties()
    return query



  def build_create_table_query_bronze_txs(self, table_name):
    self.create_namespace(table_name)
    query = f"""
      CREATE TABLE IF NOT EXISTS {table_name} (
        blockHash STRING,
        blockNumber STRING,
        confirmations STRING,
        contractAddress STRING,
        cumulativeGasUsed STRING,
        from STRING,
        functionName STRING,
        gas STRING,
        gasPrice STRING,
        gasUsed STRING,
        hash STRING,
        input STRING,
        isError STRING,
        methodId STRING,
        nonce STRING,
        timeStamp STRING,
        to STRING,
        transactionIndex STRING,
        txreceipt_status STRING,
        value STRING,
        dat_ref_hour STRING)
      USING ICEBERG
      PARTITIONED BY (dat_ref_hour)
      """
    query += self.get_iceberg_table_properties()
    return query
  

  def create_table(self, query):
    self.spark.sql(query).show()
    print(f"Table created successfully!")
    self.table_exists = True



if __name__ == "__main__":

  APP_NAME = "Create_Table_Bronze_Multiplex"
  TABLE_NAME = os.getenv("TABLE_FULLNAME")
  TABLE_MULTIPLEXED = "nessie.bronze.kafka_topics_multiplexed"
  TABLE_TXS_BATCH = "nessie.bronze.popular_contracts_txs"

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())
  
  spark = SparkUtils.get_spark_session(LOGGER, APP_NAME)
  ddl_actor = CreateIcebergBronzeTables(spark)
  ddl_query = ddl_actor.build_create_table_query_bronze_txs(TABLE_TXS_BATCH)
  ddl_actor.create_table(ddl_query)
  ddl_actor.get_table_info(TABLE_TXS_BATCH)

  ddl_query = ddl_actor.build_create_table_query_bronze_multiplexed(TABLE_MULTIPLEXED)
  ddl_actor.create_table(ddl_query)
  ddl_actor.get_table_info(TABLE_MULTIPLEXED)