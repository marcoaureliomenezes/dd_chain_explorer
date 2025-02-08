import os

from spark_utils import SparkUtils
from table_creator import TableCreator


class CreateIcebergSilverBlocksTxs(TableCreator):

  def create_table(self):
    self.create_namespace()
    self.spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
      block_timestamp TIMESTAMP           COMMENT 'Block timestamp',
      block_number LONG                   COMMENT 'Block number',
      transaction_id STRING               COMMENT 'Number of transactions',
      dt_hour_ref STRING                  COMMENT 'Partition Field with Date and hour of Kafka Message')
    USING ICEBERG
    PARTITIONED BY (dt_hour_ref)
    TBLPROPERTIES (
      'gc.enabled' = 'true',
      'write.delete.mode' = 'copy-on-write',
      'write.update.mode' = 'merge-on-read',
      'write.merge.mode' = 'merge-on-read',
      'write.metadata.delete-after-commit.enabled' = true,
      'write.metadata.previous-versions-max' = 3,
      'write.parquet.compression-codec' = 'snappy'
    )""").show()
    print(f"Table {self.table_name} created successfully!")
    self.table_exists = True
    return self


if __name__ == "__main__":

    APP_NAME = "Create_Table_Silver_Blocks_Transactions"
    TABLE_NAME = os.getenv("TABLE_FULLNAME")
    spark = SparkUtils.get_spark_session(APP_NAME)
    ddl_actor = CreateIcebergSilverBlocksTxs(spark, table_name=TABLE_NAME)
    ddl_actor.create_table()
    ddl_actor.get_table_info()



