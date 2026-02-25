# Databricks notebook source
# DDL — Remove todas as tabelas e schemas do catálogo (teardown)
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_5_delete_all_tables.py
# e ao Airflow DAG: dag_eventual_2_delete_environment.py
#
# ATENÇÃO: use somente em DEV. Irreversível em PROD.

catalog = "dd_chain_explorer_dev"
purge   = "true"

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    pass

try:
    purge = dbutils.widgets.get("purge")
except Exception:
    pass

purge_clause = "PURGE" if purge.lower() == "true" else ""

tables = [
    f"`{catalog}`.b_fast.kafka_topics_multiplexed",
    f"`{catalog}`.bronze.popular_contracts_txs",
    f"`{catalog}`.s_apps.mined_blocks_events",
    f"`{catalog}`.s_apps.blocks_fast",
    f"`{catalog}`.s_apps.transactions_fast",
    f"`{catalog}`.s_logs.apps_logs_fast",
]

views = [
    f"`{catalog}`.gold.blocks_with_tx_count",
    f"`{catalog}`.gold.top_contracts_by_volume",
    f"`{catalog}`.gold.blocks_hourly_summary",
]

schemas = [
    f"`{catalog}`.b_fast",
    f"`{catalog}`.bronze",
    f"`{catalog}`.s_apps",
    f"`{catalog}`.s_logs",
    f"`{catalog}`.gold",
]

print(f"[WARN] Dropping all tables in catalog '{catalog}' with purge={purge}")

for view in views:
    try:
        spark.sql(f"DROP VIEW IF EXISTS {view}")
        print(f"[OK] View dropped: {view}")
    except Exception as e:
        print(f"[WARN] Could not drop view {view}: {e}")

for table in tables:
    try:
        spark.sql(f"DROP TABLE IF EXISTS {table} {purge_clause}")
        print(f"[OK] Table dropped: {table}")
    except Exception as e:
        print(f"[WARN] Could not drop table {table}: {e}")

for schema in schemas:
    try:
        spark.sql(f"DROP SCHEMA IF EXISTS {schema}")
        print(f"[OK] Schema dropped: {schema}")
    except Exception as e:
        print(f"[WARN] Could not drop schema {schema}: {e}")

print(f"[DONE] Teardown complete for catalog '{catalog}'")
