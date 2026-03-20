# Databricks notebook source
# Periodic — Exporta Gold views de consumo de API keys para S3 (JSON)
# Trigger Lambda S3→DynamoDB para popular entidade CONSUMPTION no DynamoDB.

from pyspark.sql import functions as F

catalog    = dbutils.widgets.get("catalog")
s3_path    = dbutils.widgets.get("export_s3_path")

# -----------------------------------------------------------------------
# Lê Gold views de consumo de API keys
# -----------------------------------------------------------------------
df_etherscan = (
    spark.table(f"`{catalog}`.g_api_keys.etherscan_consumption")
    .withColumn("source", F.lit("etherscan"))
)

df_web3 = (
    spark.table(f"`{catalog}`.g_api_keys.web3_keys_consumption")
    .withColumn("source", F.lit("web3"))
)

df_combined = df_etherscan.unionByName(df_web3, allowMissingColumns=True)

count = df_combined.count()
print(f"[INFO] Exporting {count} rows to S3")

# -----------------------------------------------------------------------
# Escreve JSON particionado por source para trigger Lambda
# -----------------------------------------------------------------------
(
    df_combined.coalesce(1)
    .write
    .mode("overwrite")
    .json(f"{s3_path}/gold_api_keys")
)

print(f"[OK] Gold API key consumption exported to {s3_path}/gold_api_keys")
