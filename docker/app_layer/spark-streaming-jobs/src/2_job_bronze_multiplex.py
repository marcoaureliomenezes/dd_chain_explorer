import os
from spark_utils import SparkUtils
from pyspark.sql.functions import col, date_format


class MultiplexIngestor:
   
  def __init__(self, spark, table_name):
    self.spark = spark
    self.table_name = table_name


  def extract_data(self, kafka_options):
    return (
      self.spark
        .readStream
        .format("kafka")
        .options(**kafka_options)
        .load()
        .withColumn("ohour", date_format(col("timestamp"), "yyyy-MM-dd-HH"))
        .select("key","value","partition","offset","timestamp","topic", "ohour"))

  def load_data_to_console(self, df_transformed):
    return (
      df_transformed
        .writeStream
        .outputMode("append")
        .format("console")
        .trigger(processingTime='15 seconds')
        .start())

  def load_data_to_bronze(self, df_transformed, checkpoint_path):
    return (
      df_transformed
        .writeStream
        .format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .trigger(processingTime='2 minutes')
        .toTable(self.table_name))


if __name__ == "__main__":
    
  APP_NAME = "bronze_kafka_topics_multiplexed"

  KAFKA_BROKERS = os.getenv("KAFKA_BROKERS")
  consumer_group = os.getenv("CONSUMER_GROUP")
  starting_offsets = os.getenv("STARTING_OFFSETS")
  max_offsets_per_trigger = os.getenv("MAX_OFFSETS_PER_TRIGGER")
  TABLE_BRONZE = os.getenv("TABLE_BRONZE")
  checkpoint_path = "s3a://spark/checkpoints/kafka_topics_multiplexed"
  topics = "mainnet.1.mined_blocks.data,mainnet.2.orphan_blocks.data,mainnet.4.mined.txs.raw_data"
  # mainnet.0.application.logs
  kafka_options = {
  "kafka.bootstrap.servers": KAFKA_BROKERS,
  "subscribe": topics,
  "startingOffsets": starting_offsets,
  "group.id": consumer_group,
  "maxOffsetsPerTrigger": max_offsets_per_trigger,
  'failOnDataLoss': 'false'
  }

  spark = SparkUtils.get_spark_session(APP_NAME)
  engine = MultiplexIngestor(spark, TABLE_BRONZE)

  data_extracted = engine.extract_data(kafka_options)
  query = engine.load_data_to_bronze(data_extracted, checkpoint_path)
  #query = engine.load_data_to_console(data_extracted)
  query.awaitTermination()
  