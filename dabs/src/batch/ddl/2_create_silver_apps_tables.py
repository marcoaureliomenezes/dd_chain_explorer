# Databricks notebook source
# DDL — Cria tabelas Silver s_apps no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_2_create_silvers_s_apps.py

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dd_chain_explorer"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.s_apps")

# As tabelas abaixo são gerenciadas pelo pipeline DLT dm-ethereum — NÃO criar aqui.
# O DLT precisa ser o dono exclusivo (schema evolution + checkpoints):
#   - s_apps.mined_blocks_events        (← mainnet.1.mined_blocks.events)
#   - s_apps.blocks_fast                (← mainnet.2.blocks.data)
#   - s_apps.transaction_hash_ids       (← mainnet.3.block.txs.hash_id)
#   - s_apps.transactions_fast          (← mainnet.4 + mainnet.5 JOIN)
#   - s_apps.popular_contracts_ranking  (gold MV — top 100 contratos)
#   - s_apps.transactions_lambda        (gold MV — visão Lambda batch+streaming)

spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.s_apps.transactions_batch (
    contract_address  STRING,
    tx_hash           STRING,
    block_number      BIGINT,
    timestamp         TIMESTAMP,
    from_address      STRING,
    to_address        STRING,
    value             STRING,
    gas_used          BIGINT,
    ethereum_value    DOUBLE,
    ingestion_date    DATE,
    processed_ts      TIMESTAMP
  )
  USING DELTA
  PARTITIONED BY (ingestion_date)
  TBLPROPERTIES ('quality' = 'silver')
""")

print(f"[OK] Silver s_apps tables created in catalog '{catalog}'")
