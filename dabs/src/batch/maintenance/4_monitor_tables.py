# Databricks notebook source
# Maintenance — Monitora métricas das tabelas Delta

from pyspark.sql import functions as F

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dev"

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

metrics = []
for t in all_tables:
    full = f"`{catalog}`.{t}"
    try:
        count  = spark.table(full).count()
        detail = spark.sql(f"DESCRIBE DETAIL {full}").collect()[0]
        metrics.append({
            "table":             t,
            "row_count":         count,
            "num_files":         detail["numFiles"],
            "size_bytes":        detail["sizeInBytes"],
            "last_modified":     str(detail["lastModified"]),
        })
        print(f"[OK] {t}: {count:,} rows | {detail['numFiles']} files | {detail['sizeInBytes']:,} bytes")
    except Exception as e:
        print(f"[WARN] Could not query {t}: {e}")

# Display as DataFrame for notebook output
if metrics:
    display(spark.createDataFrame(metrics))
