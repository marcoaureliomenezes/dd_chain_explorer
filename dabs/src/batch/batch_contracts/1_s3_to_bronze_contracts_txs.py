# Databricks notebook source
# Batch — Carrega transações brutas de contratos (JSON do S3) → Bronze
#
# Triggered by: [dev] dm-batch-s3-to-bronze  (via DatabricksRunNowOperator)
#
# Parâmetros (notebook_params do Airflow):
#   exec_date  : fim da janela horária, formato "YYYY-MM-DDTHH"  (ex: "2026-02-25T02")
#   catalog    : catálogo Unity Catalog  (ex: "dev")
#   s3_bucket  : bucket S3 de ingestão  (ex: "dm-chain-explorer-dev-ingestion")
#   s3_prefix  : prefixo dentro do bucket  (ex: "batch")

from datetime import datetime
from pyspark.sql.types import (
    StructType, StructField,
    StringType, LongType, TimestampType, DateType,
)

# ── Parâmetros ────────────────────────────────────────────────────────────────
catalog   = dbutils.widgets.get("catalog")
s3_bucket = dbutils.widgets.get("s3_bucket")
s3_prefix = dbutils.widgets.get("s3_prefix") if "s3_prefix" in [w.name for w in dbutils.widgets.getAll()] else "batch"
exec_date = dbutils.widgets.get("exec_date")  # "2026-02-25T02"

# ── Derivar caminho S3 ─────────────────────────────────────────────────────────
# O script Docker grava: {prefix}/year={Y}/month={M}/day={D}/hour={H}/txs_{addr}.json
# usando datetime.fromtimestamp(end_timestamp) → sem zero-pad em month/day/hour
dt_end = datetime.strptime(exec_date, "%Y-%m-%dT%H")
s3_path = (
    f"s3://{s3_bucket}/{s3_prefix}"
    f"/year={dt_end.year}/month={dt_end.month}"
    f"/day={dt_end.day}/hour={dt_end.hour}/"
)
print(f"[INFO] Lendo S3: {s3_path}")

# ── Schema (espelha o Row do script Docker) ────────────────────────────────────
schema = StructType([
    StructField("contract_address", StringType(),   True),
    StructField("tx_hash",          StringType(),   True),
    StructField("block_number",     LongType(),     True),
    StructField("timestamp",        TimestampType(), True),
    StructField("from_address",     StringType(),   True),
    StructField("to_address",       StringType(),   True),
    StructField("value",            StringType(),   True),
    StructField("gas_used",         LongType(),     True),
    StructField("input",            StringType(),   True),
    StructField("ingestion_date",   DateType(),     True),
])

# ── Ler JSON (cada arquivo é um array de objetos) ─────────────────────────────
try:
    df_raw = (
        spark.read
        .option("multiLine", "true")
        .schema(schema)
        .json(s3_path)
    )
    count = df_raw.count()
except Exception as e:
    # Caminho não existe (hora sem transações) → não é erro
    print(f"[WARN] Nenhum dado encontrado em {s3_path}: {e}")
    count = 0

print(f"[INFO] {count} transações encontradas no S3")

if count == 0:
    print("[WARN] Sem dados — pulando carga Bronze")
else:
    # ── Upsert em Bronze (idempotente por tx_hash) ─────────────────────────────
    df_raw.createOrReplaceTempView("staged_contracts_txs")

    spark.sql(f"""
        MERGE INTO `{catalog}`.bronze.popular_contracts_txs AS tgt
        USING staged_contracts_txs AS src
        ON tgt.tx_hash = src.tx_hash
        WHEN NOT MATCHED THEN INSERT *
    """)

    print(f"[OK] {count} linhas mergeadas em `{catalog}`.bronze.popular_contracts_txs")
