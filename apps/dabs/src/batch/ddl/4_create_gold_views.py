# Databricks notebook source
# DDL — Cria views Gold no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_4_create_gold_views.py

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dd_chain_explorer"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.gold")

spark.sql(f"""
  CREATE OR REPLACE VIEW `{catalog}`.gold.blocks_with_tx_count AS
  SELECT
    b.block_number,
    b.block_hash,
    b.miner,
    b.gas_used,
    b.gas_limit,
    b.base_fee_per_gas,
    b.transaction_count,
    b.block_time     AS event_time
  FROM `{catalog}`.s_apps.blocks_fast b
""")

spark.sql(f"""
  CREATE OR REPLACE VIEW `{catalog}`.gold.top_contracts_by_volume AS
  SELECT
    to_address           AS contract_address,
    COUNT(*)             AS tx_count,
    SUM(CAST(value AS DOUBLE)) AS total_value_wei,
    DATE_TRUNC('hour', _ingested_at) AS hour_bucket
  FROM `{catalog}`.s_apps.transactions_fast
  WHERE to_address IS NOT NULL
  GROUP BY to_address, DATE_TRUNC('hour', _ingested_at)
""")

spark.sql(f"""
  CREATE OR REPLACE VIEW `{catalog}`.gold.blocks_hourly_summary AS
  SELECT
    DATE_TRUNC('hour', block_time) AS hour_bucket,
    COUNT(*)                        AS block_count,
    AVG(transaction_count)          AS avg_tx_per_block,
    AVG(gas_used)                   AS avg_gas_used,
    AVG(base_fee_per_gas)           AS avg_base_fee
  FROM `{catalog}`.s_apps.blocks_fast
  GROUP BY DATE_TRUNC('hour', block_time)
""")

print(f"[OK] Gold views created in catalog '{catalog}'")
