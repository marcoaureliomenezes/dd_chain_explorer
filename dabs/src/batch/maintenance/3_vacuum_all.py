# Databricks notebook source
# Maintenance — VACUUM todas as tabelas

catalog         = dbutils.widgets.get("catalog")
retention_hours = int(dbutils.widgets.get("retention_hours") if "retention_hours" in [w.name for w in dbutils.widgets.getAll()] else "168")

# Disable retention check for test environments (DEV only)
# spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")

all_tables = [
    "b_fast.kafka_topics_multiplexed",
    "bronze.popular_contracts_txs",
    "s_apps.transactions_fast",
    "s_apps.blocks_fast",
    "s_apps.mined_blocks_events",
    "s_logs.apps_logs_fast",
]

for t in all_tables:
    full = f"`{catalog}`.{t}"
    print(f"[INFO] VACUUM {full} RETAIN {retention_hours} HOURS ...")
    spark.sql(f"VACUUM {full} RETAIN {retention_hours} HOURS")
    print(f"[OK]   {full} vacuumed")
