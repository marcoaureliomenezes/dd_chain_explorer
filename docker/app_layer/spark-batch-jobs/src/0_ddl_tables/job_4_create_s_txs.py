import os

from spark_utils import SparkUtils
from table_creator import TableCreator


class CreateIcebergSilverTxs(TableCreator):

  def create_table(self):
    self.create_namespace()
    query = f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
      ingestion_time TIMESTAMP          COMMENT 'Kafka timestamp',  
      block_number LONG                 COMMENT 'Block number',
      hash STRING                       COMMENT 'Block hash',   
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
    query += self.get_iceberg_table_properties()
    self.spark.sql(query).show()
    print(f"Table {self.table_name} created successfully!")
    self.table_exists = True
    return self


if __name__ == "__main__":

    APP_NAME = "Create_Table_Silver_Transactions"
    TABLE_NAME = os.getenv("TABLE_FULLNAME")
    spark = SparkUtils.get_spark_session(APP_NAME)
    for table_name in [f"{TABLE_NAME}_contracts", f"{TABLE_NAME}_p2p"]:
        ddl_actor = CreateIcebergSilverTxs(spark, table_name=table_name)
        ddl_actor.create_table()
        ddl_actor.get_table_info()




