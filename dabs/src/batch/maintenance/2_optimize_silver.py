# Databricks notebook source
# Maintenance — OPTIMIZE + ZORDER tabelas Silver

catalog = dbutils.widgets.get("catalog")

tables = [
    ("s_apps", "transactions_fast",    "block_number"),
    ("s_apps", "blocks_fast",          "event_time"),
    ("s_apps", "mined_blocks_events",  "event_time"),
    ("s_logs", "apps_logs_fast",       "job_name"),
]

for schema, table, zorder_col in tables:
    full = f"`{catalog}`.{schema}.{table}"
    print(f"[INFO] Optimizing {full} ...")
    spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
    print(f"[OK]   {full} optimized")
