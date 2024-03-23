# Exemplo em Python (PySpark)
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, split, count, window
from pyspark.sql.types import StructType, StringType, IntegerType
from datetime import datetime, timedelta

spark = SparkSession \
    .builder \
    .appName("MySparkApp") \
    .master("spark://spark-master:7077") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")


kafka_options = {
    "kafka.bootstrap.servers": "broker-1:29092,broker-2:29093,broker-3:29094",
    "subscribe": "mainnet.application.logs",
    "startingOffsets": "earliest"
}

# Configurações do ScyllaDB
scylla_options = {
    "spark.cassandra.connection.host": "scylladb",
    "spark.cassandra.connection.port": "9042",
    "keyspace": "operations",
    "table": "api_keys_node_providers"
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

df_windowed_counts = (
  df_logs
    .withWatermark("timestamp", "1 day")
    .groupBy(col("api_key"), window(col("timestamp"), "1 day"))
    .agg(count("*").alias("count"))
    .select(
      col("api_key").alias("name").cast(StringType()), 
      col("window.start").alias("start").cast(StringType()), 
      col("window.end").alias("end").cast(StringType()), 
      col("count").alias("num_req_1d").cast(IntegerType())
    )

)

_ = (
  df_windowed_counts.writeStream
        .format("org.apache.spark.sql.cassandra")
        .option("checkpointLocation", "/tmp/checkpoint")
        .trigger(processingTime="2 seconds")
        .outputMode("update")
        .foreachBatch(lambda df, epoch_id: 
                      df.write.mode("append")
                        .format("org.apache.spark.sql.cassandra")
                        .options(**scylla_options).save()
        )
        .start()
        .awaitTermination()


        .cast(StringType())
)

# query = df_windowed_counts \
#     .writeStream \
#     .outputMode("complete") \
#     .format("console") \
#     .start()

# Suponha que eu tenho 2 colunas em 1 dataframe em spark streaming:
# timestamp e value. a coluna value, quando quebrada por ; tem em seu segundo campo 1 valor. Gostaria de fazer uma window function de 1 dia e contar quantas vezes esse valor aparece, usando o timestamp. Como posso fazer isso no pyspark?

# Exemplo de como fazer isso:


# query.awaitTermination()