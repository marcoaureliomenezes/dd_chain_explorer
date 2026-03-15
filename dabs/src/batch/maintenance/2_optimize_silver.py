# Databricks notebook source
# Maintenance — OPTIMIZE + ZORDER tabelas Silver

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dev"

tables = [
    ("s_apps", "transactions_fast",           "block_number"),
    ("s_apps", "blocks_fast",                 "event_time"),
    ("s_apps", "mined_blocks_events",         "event_time"),
    ("s_apps", "transactions_batch",          "block_number"),
    ("s_apps", "popular_contracts_ranking",   "contract_address"),
    ("s_apps", "transactions_lambda",         "contract_address"),
    ("s_logs", "application_logs",            "logger"),
    ("s_logs", "apps_logs_fast",              "job_name"),
    ("s_logs", "api_key_consumption",         "provider"),
]

for schema, table, zorder_col in tables:
    full = f"`{catalog}`.{schema}.{table}"
    print(f"[INFO] Optimizing {full} ...")
    try:
        spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
        print(f"[OK]   {full} optimized")
    except Exception as e:
        print(f"[WARN] Could not optimize {full}: {e}")
