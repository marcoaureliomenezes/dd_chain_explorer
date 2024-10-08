from utils.spark_utils import SparkUtils
from utils.schema_registry_utils import SchemaRegistryUtils


class RawToBronzeLogs:
   
  def __init__(self, spark, input_path, bronze_table):
    self.spark = spark
    self.input_path = input_path
    self.bronze_table = bronze_table


  def extract_data(self, avro_schema: str):
    df_simple_transactions = (
      self.spark.readStream
      .format("parquet")
      .schema(avro_schema)
      .option("path", self.input_path)
      .load()
    )
    return df_simple_transactions


  def transform_data(self, df_stream):
    return df_stream


  def load_data_to_console(self, df_transformed):
    write_stream_query = (
      df_transformed
        .writeStream
        .outputMode("complete")
        .format("console")
        .start()
        .awaitTermination()
    )
    return write_stream_query
      

  def load_data_to_bronze(self, df_transformed, checkpoint_location):
    query = (
      df_transformed.writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_location)
        .option("path", self.bronze_table)
        .start()
    )
    return query


if __name__ == "__main__":
    
  APP_NAME = "RAW_TO_BRONZE_LOGS"
  SCHEMA_REGISTRY_URL = "http://schema-registry:8081"
  SCHEMA_REGISTRY_SUBJECT = "mainnet.application.logs-value"
  INPUT_PATH = "hdfs://namenode:9000/raw/application_logs/mainnet.application.logs"
  BRONZE_TABLE = "b_apps.app_logs"

  spark = SparkUtils.get_spark_session(APP_NAME)
 
  sc_client = SchemaRegistryUtils.get_schema_registry_client(SCHEMA_REGISTRY_URL)
  avro_schema_logs = SchemaRegistryUtils.get_avro_schema(sc_client, SCHEMA_REGISTRY_SUBJECT)


  engine = RawToBronzeLogs(spark, INPUT_PATH, BRONZE_TABLE, avro_schema_logs)
  data_extracted = engine.extract_data(avro_schema_logs)
  query = engine.transform_data(data_extracted)
  write_stream_query = engine.load_data_to_console(query)
  write_stream_query.awaitTermination()