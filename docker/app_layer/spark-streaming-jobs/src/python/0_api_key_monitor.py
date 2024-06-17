# Exemplo em Python (PySpark)
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, split, count, window, max
from pyspark.sql.types import StructType, StringType, IntegerType
from datetime import datetime, timedelta

spark_url = "spark://spark-master:7077"
spark_app = "Handle_Simple_Transactions"
kafka_brokers = "broker-1:29092,broker-2:29093,broker-3:29094"
topic_subscribe = "mainnet.application.logs"
starting_offsets = "earliest"
group_id = "api_key_consumer_1"
max_offsets_per_trigger = "1000"

kassandra_host = "scylladb"
kassandra_port = "9042"
kassandra_keyspace = "operations"
kassandra_table = "api_keys_node_providers"

spark = (
  SparkSession \
    .builder \
    .appName("API_KEY_Monitor")
    .master("spark://spark-master:7077")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")

kafka_options = {
    "kafka.bootstrap.servers": kafka_brokers,
    "subscribe": topic_subscribe,
    "startingOffsets": starting_offsets,
    "group.id": group_id,
    "maxOffsetsPerTrigger": max_offsets_per_trigger
}

scylla_options = {
    "spark.cassandra.connection.host": kassandra_host,
    "spark.cassandra.connection.port": kassandra_port,
    "keyspace": kassandra_keyspace,
    "table": kassandra_table
}

kafka_options = {
    "kafka.bootstrap.servers": "broker-1:29092,broker-2:29093,broker-3:29094",
    "subscribe": "mainnet.application.logs",
    "startingOffsets": "latest",
    "failOnDataLoss": "false",
    "maxOffsetsPerTrigger": "20000",
}

# Configurações do ScyllaDB
scylla_options = {
    "spark.cassandra.connection.host": "scylladb",
    "spark.cassandra.connection.port": "9042",
    "keyspace": "operations",
    "table": "api_keys_node_providers",
}

# Leia os dados do Kafka
df_logs = (
  spark
    .readStream
    .format("kafka")
    .options(**kafka_options)
    .load()
    .select(col("timestamp"), col("value").cast(StringType()))
    .filter(col("value").startswith("API_request"))
    .withColumn("api_key", split(col("value"), ";").getItem(1))
    .select(col("timestamp"), col("api_key"))
)

window_1D = window(col("timestamp"), "1 day")

df_windowed_counts = (
  df_logs
    .withWatermark("timestamp", "1 day")
    .groupBy(col("api_key"), window_1D)
    .agg(count("*").alias("count"), max("timestamp").alias("max_timestamp"))
    .select(
      col("api_key").alias("name").cast(StringType()), 
      col("window.start").alias("start").cast(StringType()), 
      col("window.end").alias("end").cast(StringType()), 
      col("count").alias("num_req_1d").cast(IntegerType()),
      col("max_timestamp").alias("last_req").cast(StringType())
    )

)

_ = (
  df_windowed_counts.writeStream
        .format("org.apache.spark.sql.cassandra")
        .option("checkpointLocation", "/tmp/dm_checkpoint")
        .outputMode("update")
        .trigger(processingTime="1 seconds")
        .foreachBatch(lambda df, epoch_id: 
                      df.write.mode("append")
                        .format("org.apache.spark.sql.cassandra")
                        .options(**scylla_options).save()
        )
        .start()
        .awaitTermination()
)

