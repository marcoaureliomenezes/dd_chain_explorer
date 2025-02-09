import os

from spark_utils import SparkUtils
from table_creator import TableCreator


class CreateIcebergBronzeMultiplex(TableCreator):


  def create_table(self):
    self.create_namespace()
    query = f"""
      CREATE TABLE IF NOT EXISTS {self.table_name} (
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
    self.spark.sql(query).show()
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
