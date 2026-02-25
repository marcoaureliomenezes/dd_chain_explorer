# Databricks notebook source
# Batch — Bronze popular_contracts_txs → Silver s_apps.transactions_batch
#
# Triggered by: [dev] dm-batch-bronze-to-silver  (via DatabricksRunNowOperator)
#
# Parâmetros (notebook_params do Airflow):
#   exec_date : fim da janela horária, formato "YYYY-MM-DDTHH"  (ex: "2026-02-25T02")
#   catalog   : catálogo Unity Catalog  (ex: "dev")

from datetime import datetime
from pyspark.sql import functions as F

# ── Parâmetros ────────────────────────────────────────────────────────────────
catalog   = dbutils.widgets.get("catalog")
exec_date = dbutils.widgets.get("exec_date")  # "2026-02-25T02"

dt_end = datetime.strptime(exec_date, "%Y-%m-%dT%H")
ingestion_date = dt_end.strftime("%Y-%m-%d")

print(f"[INFO] Processando Bronze → Silver para ingestion_date = {ingestion_date}")

# ── Ler Bronze filtrado por data ───────────────────────────────────────────────
df_bronze = (
    spark.table(f"`{catalog}`.bronze.popular_contracts_txs")
    .filter(F.col("ingestion_date") == F.lit(ingestion_date).cast("date"))
)

count = df_bronze.count()
print(f"[INFO] {count} linhas Bronze para data {ingestion_date}")

if count == 0:
    print("[WARN] Bronze vazio para esta data — pulando Silver")
else:
    # ── Transformação ──────────────────────────────────────────────────────────
    # ethereum_value: converte value (wei string) → ETH  (value / 1e18)
    df_silver = (
        df_bronze
        .withColumn(
            "ethereum_value",
            (F.col("value").cast("decimal(38,0)") / F.lit(1e18)).cast("double"),
        )
        .withColumn("processed_ts", F.current_timestamp())
        .select(
            "contract_address",
            "tx_hash",
            "block_number",
            "timestamp",
            "from_address",
            "to_address",
            "value",
            "gas_used",
            "ethereum_value",
            "ingestion_date",
            "processed_ts",
        )
    )

    # ── Upsert em Silver (idempotente por tx_hash) ─────────────────────────────
    df_silver.createOrReplaceTempView("staged_silver_txs")

    spark.sql(f"""
        MERGE INTO `{catalog}`.s_apps.transactions_batch AS tgt
        USING staged_silver_txs AS src
        ON tgt.tx_hash = src.tx_hash
        WHEN MATCHED THEN UPDATE SET
            tgt.ethereum_value = src.ethereum_value,
            tgt.processed_ts   = src.processed_ts
        WHEN NOT MATCHED THEN INSERT *
    """)

    print(f"[OK] {count} linhas mergeadas em `{catalog}`.s_apps.transactions_batch")

    # ── Verificação ────────────────────────────────────────────────────────────
    total = spark.table(f"`{catalog}`.s_apps.transactions_batch").count()
    print(f"[INFO] Total em s_apps.transactions_batch: {total} linhas")
