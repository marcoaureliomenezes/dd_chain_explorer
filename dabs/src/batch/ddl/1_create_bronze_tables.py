# Databricks notebook source
# DDL — Cria tabelas Bronze no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_1_create_bronze_tables.py

import os
from pyspark.sql import SparkSession

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dd_chain_explorer"
spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.b_ethereum")

# kafka_topics_multiplexed é gerenciada pelo pipeline DLT (pipeline_bronze_multiplex).
# NÃO criar aqui — o DLT precisa ser o dono exclusivo da tabela.

# popular_contracts_txs — batch ingestão de transações de contratos populares
spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.b_ethereum.popular_contracts_txs (
    contract_address  STRING,
    tx_hash           STRING,
    block_number      BIGINT,
    timestamp         TIMESTAMP,
    from_address      STRING,
    to_address        STRING,
    value             STRING,
    gas_used          BIGINT,
    input             STRING,
    ingestion_date    DATE
  )
  USING DELTA
  PARTITIONED BY (ingestion_date)
  TBLPROPERTIES ('quality' = 'bronze')
""")

print(f"[OK] Bronze tables created in catalog '{catalog}' (schema: b_ethereum)")
