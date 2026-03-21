# Databricks notebook source
# DDL — Cria tabela Silver s_logs no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_3_create_silver_table_logs.py

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dd_chain_explorer"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.s_logs")

spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.s_logs.apps_logs_fast (
    level           STRING,
    logger          STRING,
    message         STRING,
    timestamp       BIGINT,
    job_name        STRING,
    api_key         STRING,
    event_time      TIMESTAMP,
    kafka_timestamp TIMESTAMP
  )
  USING DELTA
  PARTITIONED BY (job_name)
  TBLPROPERTIES ('quality' = 'silver')
""")

# As tabelas abaixo são gerenciadas pelo pipeline DLT dm-ethereum — NÃO criar aqui:
#   - s_logs.application_logs    (← mainnet.0.application.logs)
#   - s_logs.api_key_consumption (← extraído dos logs de aplicação)

print(f"[OK] Silver s_logs tables created in catalog '{catalog}'")
