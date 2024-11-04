import os
from spark_utils import SparkUtils



class MultiplexIngestor:
   
  def __init__(self, spark, table_name):
    self.spark = spark
    self.table_name = table_name

  def create_table(self):
    self.spark.sql("CREATE NAMESPACE IF NOT EXISTS nessie.bronze")
    self.spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {self.table_name} (
    key binary,
    value binary,
    partition int,
    offset long,
    timestamp timestamp,
    topic string)
    USING ICEBERG 
    PARTITIONED BY (topic, hour(timestamp))""").show()
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
  consumer_group = os.getenv("CONSUMER_GROUP", "cg_war")
  starting_offsets = os.getenv("STARTING_OFFSETS", "latest")
  max_offsets_per_trigger = os.getenv("MAX_OFFSETS_PER_TRIGGER", 1000)
  bronze_table = 'nessie.bronze.data_multiplexed'
  checkpoint_path = "s3a://sistemas/checkpoints/multiplex_bronze"
  topics = ",mainnet.1.mined_blocks.data,mainnet.2.orphan_blocks.data,mainnet.4.mined.txs.raw_data"
  # mainnet.0.application.logs
  kafka_options = {
  "kafka.bootstrap.servers": kafka_cluster,
  "subscribe": topics,
  "startingOffsets": starting_offsets,
  "group.id": consumer_group,
  "maxOffsetsPerTrigger": max_offsets_per_trigger,
  'failOnDataLoss': 'false'
  }


  spark = SparkUtils.get_spark_session(APP_NAME)
  engine = MultiplexIngestor(spark, bronze_table)

  engine.create_table()
  data_extracted = engine.extract_data(kafka_options)
  query = engine.load_data_to_bronze(data_extracted, checkpoint_path)
  #query = engine.load_data_to_console(data_extracted)
  query.awaitTermination()
  