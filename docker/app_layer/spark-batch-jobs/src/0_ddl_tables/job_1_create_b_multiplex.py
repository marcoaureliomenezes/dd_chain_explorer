import os

from spark_utils import SparkUtils
from table_creator import TableCreator


class CreateIcebergBronzeMultiplex(TableCreator):


  def create_table(self):
    self.create_namespace()
    self.spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
    key BINARY                    COMMENT 'Key',
    value BINARY                  COMMENT 'Kafka Value Binary',   
    partition INT                 COMMENT 'Kafka Message Partition',
    offset LONG                   COMMENT 'Kafka Message Offset',
    timestamp TIMESTAMP           COMMENT 'Kafka Message Timestamp',
    topic STRING                  COMMENT 'Partition Field Kafka Topic',
    ohour STRING                  COMMENT 'Partition Field with Date and hour')
    USING ICEBERG 
    PARTITIONED BY (topic, ohour)
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

    APP_NAME = "Create_Table_Bronze_Multiplex"
    TABLE_NAME = os.getenv("TABLE_FULLNAME")
    spark = SparkUtils.get_spark_session(APP_NAME)
    ddl_actor = CreateIcebergBronzeMultiplex(spark, table_name=TABLE_NAME)
    ddl_actor.create_table()
    ddl_actor.get_table_info()
