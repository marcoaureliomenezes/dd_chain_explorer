# Databricks notebook source
# DDL — Cria tabelas Silver s_apps no Unity Catalog
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_2_create_silvers_s_apps.py

catalog = dbutils.widgets.get("catalog") if "catalog" in [w.name for w in dbutils.widgets.getAll()] else "dd_chain_explorer"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.s_apps")

spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.s_apps.mined_blocks_events (
    block_number        BIGINT  NOT NULL,
    block_hash          STRING,
    parent_hash         STRING,
    block_timestamp     BIGINT,
    transaction_count   INT,
    event_time          TIMESTAMP,
    kafka_timestamp     TIMESTAMP
  )
  USING DELTA
  TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true', 'quality' = 'silver')
""")

spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.s_apps.blocks_fast (
    number              BIGINT,
    hash                STRING,
    parent_hash         STRING,
    timestamp           BIGINT,
    miner               STRING,
    difficulty          BIGINT,
    total_difficulty    STRING,
    size                INT,
    gas_used            BIGINT,
    gas_limit           BIGINT,
    transaction_count   INT,
    base_fee_per_gas    BIGINT,
    event_time          TIMESTAMP,
    kafka_timestamp     TIMESTAMP
  )
  USING DELTA
  TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true', 'quality' = 'silver')
""")

spark.sql(f"""
  CREATE TABLE IF NOT EXISTS `{catalog}`.s_apps.transactions_fast (
    hash                    STRING,
    block_number            BIGINT,
    block_hash              STRING,
    transaction_index       INT,
    from_address            STRING,
    to_address              STRING,
    value                   STRING,
    gas                     BIGINT,
    gas_price               BIGINT,
    nonce                   BIGINT,
    input                   STRING,
    type                    INT,
    max_fee_per_gas         BIGINT,
    max_priority_fee_per_gas BIGINT,
    kafka_timestamp         TIMESTAMP
  )
  USING DELTA
  PARTITIONED BY (block_number)
  TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true', 'quality' = 'silver')
""")

print(f"[OK] Silver s_apps tables created in catalog '{catalog}'")
