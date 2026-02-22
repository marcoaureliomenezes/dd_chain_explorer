# Databricks notebook source
# DDL — Cria tabelas Bronze no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_1_create_bronze_tables.py

import os
from pyspark.sql import SparkSession

catalog  = dbutils.widgets.get("catalog") if "catalog" in [w.name for w in dbutils.widgets.getAll()] else "dd_chain_explorer"
spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.b_fast")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.bronze")

# kafka_topics_multiplexed — landing zone de todos os tópicos
spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.b_fast.kafka_topics_multiplexed (
    topic_name      STRING  NOT NULL,
    partition       INT,
    offset          BIGINT,
    timestamp       TIMESTAMP,
    key             STRING,
    value           STRING
  )
  USING DELTA
  PARTITIONED BY (topic_name)
  TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'bronze'
  )
""")

# popular_contracts_txs — batch ingestão de transações de contratos populares
spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.bronze.popular_contracts_txs (
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

print(f"[OK] Bronze tables created in catalog '{catalog}'")
