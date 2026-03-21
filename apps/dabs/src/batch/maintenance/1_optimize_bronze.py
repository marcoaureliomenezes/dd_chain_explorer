# Databricks notebook source
# Maintenance — OPTIMIZE + ZORDER tabelas Bronze

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dev"

tables = [
    ("b_ethereum", "kafka_topics_multiplexed", "kafka_timestamp"),
    ("b_ethereum", "popular_contracts_txs",    "contract_address"),
]

for schema, table, zorder_col in tables:
    full = f"`{catalog}`.{schema}.{table}"
    print(f"[INFO] Optimizing {full} ...")
    try:
        spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
        print(f"[OK]   {full} optimized")
    except Exception as e:
        print(f"[WARN] Could not optimize {full}: {e}")
