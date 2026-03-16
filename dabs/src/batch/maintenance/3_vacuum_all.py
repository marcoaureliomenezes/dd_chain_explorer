# Databricks notebook source
# Maintenance — VACUUM todas as tabelas

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dev"
try:
    retention_hours = int(dbutils.widgets.get("retention_hours"))
except Exception:
    retention_hours = 168

# Disable retention check for test environments (DEV only)
# spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")

all_tables = [
    "b_ethereum.kafka_topics_multiplexed",
    "b_ethereum.popular_contracts_txs",
    "s_apps.transactions_fast",
    "s_apps.blocks_fast",
    "s_apps.mined_blocks_events",
    "s_apps.transaction_hash_ids",
    "s_apps.transactions_batch",
    "s_apps.popular_contracts_ranking",
    "s_apps.transactions_lambda",
    "s_logs.application_logs",
    "s_logs.apps_logs_fast",
    "s_logs.api_key_consumption",
]

for t in all_tables:
    full = f"`{catalog}`.{t}"
    print(f"[INFO] VACUUM {full} RETAIN {retention_hours} HOURS ...")
    try:
        spark.sql(f"VACUUM {full} RETAIN {retention_hours} HOURS")
        print(f"[OK]   {full} vacuumed")
    except Exception as e:
        print(f"[WARN] Could not vacuum {full}: {e}")
