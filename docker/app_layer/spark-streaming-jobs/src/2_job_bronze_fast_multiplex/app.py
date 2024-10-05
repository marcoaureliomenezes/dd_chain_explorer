import os
from spark_utils import SparkUtils



class MultiplexIngestor:
   
  def __init__(self, spark, table_name):
    self.spark = spark
    self.table_name = table_name

  def create_table(self):
    self.spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
    key binary,
    value binary,
    partition int,
    offset long,
    timestamp timestamp,
    topic string) 
    USING ICEBERG PARTITIONED BY (topic)""").show()
    spark.table(self.table_name).printSchema()
    
  def extract_data(self, kafka_options):
    return (
      self.spark
        .readStream
        .format("kafka")
        .options(**kafka_options)
        .load()
        .select("key","value","partition","offset","timestamp","topic"))

  def load_data_to_console(self, df_transformed):
    return (
      df_transformed
        .writeStream
        .outputMode("append")
        .format("console")
        .start()
        .awaitTermination())

  def load_data_to_bronze(self, df_transformed, checkpoint_path):
    return (
      df_transformed
        .writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .toTable(bronze_table))



if __name__ == "__main__":
    
  APP_NAME = "bronze_multiplex"

  kafka_cluster = os.getenv("KAFKA_BROKERS", "broker:29092")
  consumer_group = os.getenv("CG_API_KEY_CONSUME", "cg_war")
  starting_offsets = os.getenv("STARTING_OFFSETS", "latest")
  max_offsets_per_trigger = os.getenv("MAX_OFFSETS_PER_TRIGGER", 1000)
  bronze_table = 'nessie.test'
  checkpoint_path = "s3a://sistemas/checkpoints/multiplex_bronze"


  kafka_options = {
  "kafka.bootstrap.servers": kafka_cluster,
  "subscribe": "mainnet.mined.block.metadata,mainnet.mined.txs.token.transfer",
  "startingOffsets": starting_offsets,
  "group.id": consumer_group,
  "maxOffsetsPerTrigger": max_offsets_per_trigger 
  }

  spark = SparkUtils.get_spark_session(APP_NAME)
  engine = MultiplexIngestor(spark, bronze_table)

  engine.create_table()
  data_extracted = engine.extract_data(kafka_options)
  query = engine.load_data_to_bronze(data_extracted, checkpoint_path)
  #query = engine.load_data_to_console(data_transformed)
  query.awaitTermination()
  