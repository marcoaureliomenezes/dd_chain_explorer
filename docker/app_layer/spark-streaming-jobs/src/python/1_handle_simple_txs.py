# Exemplo em Python (PySpark)
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StringType, IntegerType, StructField, LongType
from datetime import datetime, timedelta


spark_url = "spark://spark-master:7077"
spark_app = "Handle_Simple_Transactions"
kafka_brokers = "broker-1:29092,broker-2:29093,broker-3:29094"
topic_subscribe = "mainnet.mined.tx.1.native_token_transfer"
starting_offsets = "latest"
group_id = "simple_tx_1"
max_offsets_per_trigger = "20"


kassandra_host = "scylladb"
kassandra_port = "9042"
kassandra_keyspace = "mainnet"
kassandra_table = "user_simple_transactions"

spark = (
  SparkSession
    .builder
    .appName(spark_app)
    .master(spark_url)
    .getOrCreate()
)

simple_transaction_schema = StructType([
    StructField("accessList", StringType()),
    StructField("blockHash", StringType()),
    StructField("blockNumber", LongType()),
    StructField("chainId", LongType()),
    StructField("from", StringType()),
    StructField("gas", LongType()),
    StructField("gasPrice", LongType()),
    StructField("hash", StringType()),
    StructField("input", StringType()),
    StructField("maxFeePerGas", LongType()),
    StructField("maxPriorityFeePerGas", LongType()),
    StructField("nonce", LongType()),
    StructField("r", StringType()),
    StructField("s", StringType()),
    StructField("to", StringType()),
    StructField("transactionIndex", LongType()),
    StructField("type", IntegerType()),
    StructField("v", IntegerType()),
    StructField("value", LongType()),
    StructField("yParity", IntegerType())
])


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

# Leia os dados do Kafka
df_simple_transactions = (
  spark
    .readStream
    .format("kafka")
    .options(**kafka_options)
    .load()
    .select(col("timestamp"), col("value").cast(StringType()).alias("value"))
    .withColumn("data", from_json(col("value"), simple_transaction_schema))
    .select("data.*")
    .select("blockNumber", "from", "to", "value", "gas", "gasPrice", "transactionIndex")
)


query = (
  df_simple_transactions
    .writeStream
    .outputMode("update")
    .format("console")
    .start()
    .awaitTermination()
)

query.awaitTermination()