# Databricks notebook source
# DDL — Cria tabela Silver s_logs no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_3_create_silver_table_logs.py

catalog = dbutils.widgets.get("catalog") if "catalog" in [w.name for w in dbutils.widgets.getAll()] else "dd_chain_explorer"
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

print(f"[OK] Silver s_logs tables created in catalog '{catalog}'")
