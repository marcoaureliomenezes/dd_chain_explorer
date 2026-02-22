# Databricks notebook source
# Maintenance — Monitora métricas das tabelas Delta

from pyspark.sql import functions as F

catalog = dbutils.widgets.get("catalog")

all_tables = [
    "b_fast.kafka_topics_multiplexed",
    "bronze.popular_contracts_txs",
    "s_apps.transactions_fast",
    "s_apps.blocks_fast",
    "s_apps.mined_blocks_events",
    "s_logs.apps_logs_fast",
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
