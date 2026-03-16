# Databricks notebook source
# Periodic — Identifica contratos Ethereum populares
# Equivalente ao AS-IS: spark-batch-jobs/periodic_spark_processing/1_get_popular_contracts.py

from pyspark.sql import functions as F
import boto3

catalog               = dbutils.widgets.get("catalog")
dynamodb_table        = dbutils.widgets.get("dynamodb_table")
try:
    lookback_hours = int(dbutils.widgets.get("lookback_hours"))
except Exception:
    lookback_hours = 6
top_n                 = 50

# -----------------------------------------------------------------------
# Lê transações Silver e identifica contratos mais chamados
# -----------------------------------------------------------------------
df_popular = (
    spark.table(f"`{catalog}`.s_apps.transactions_fast")
    .filter(F.col("to_address").isNotNull())
    .filter(F.col("kafka_timestamp") >= F.date_sub(F.current_timestamp(), 1))
    .groupBy("to_address")
    .agg(
        F.count("*").alias("tx_count"),
        F.max("kafka_timestamp").alias("last_seen"),
    )
    .orderBy(F.desc("tx_count"))
    .limit(top_n)
)

contracts = df_popular.collect()
print(f"[INFO] Found {len(contracts)} popular contracts")

# -----------------------------------------------------------------------
# Persiste no DynamoDB (single-table design: PK=CONTRACT, SK={address})
# -----------------------------------------------------------------------
dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(dynamodb_table)

with table.batch_writer() as batch:
    for row in contracts:
        batch.put_item(Item={
            "pk":               "CONTRACT",
            "sk":               row["to_address"],
            "tx_count":         str(row["tx_count"]),
            "last_seen":        str(row["last_seen"]),
        })

print(f"[OK] {len(contracts)} popular contracts written to DynamoDB table '{dynamodb_table}'")
