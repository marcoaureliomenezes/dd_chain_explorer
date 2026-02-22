# Databricks notebook source
# Maintenance — OPTIMIZE + ZORDER tabelas Bronze

catalog = dbutils.widgets.get("catalog")

tables = [
    ("b_fast",  "kafka_topics_multiplexed", "topic_name"),
    ("bronze",  "popular_contracts_txs",    "contract_address"),
]

for schema, table, zorder_col in tables:
    full = f"`{catalog}`.{schema}.{table}"
    print(f"[INFO] Optimizing {full} ...")
    spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
    print(f"[OK]   {full} optimized")
