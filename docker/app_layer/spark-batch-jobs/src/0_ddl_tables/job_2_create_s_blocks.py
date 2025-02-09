import os

from spark_utils import SparkUtils
from table_creator import TableCreator


class CreateIcebergSilverBlocks(TableCreator):

  def create_table(self):
    self.create_namespace()
    query = f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
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
    query += self.get_iceberg_table_properties()
    self.spark.sql(query).show()
    print(f"Table {self.table_name} created successfully!")
    self.table_exists = True
    return self



if __name__ == "__main__":

    APP_NAME = "Create_Table_Silver_Blocks"
    TABLE_NAME = os.getenv("TABLE_FULLNAME")
    spark = SparkUtils.get_spark_session(APP_NAME)
    ddl_actor = CreateIcebergSilverBlocks(spark, table_name=TABLE_NAME)
    ddl_actor.create_table()
    ddl_actor.get_table_info()
