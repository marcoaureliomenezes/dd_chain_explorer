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
#
# Nota sobre o schema:
#   O script Docker (1_capture_and_ingest_contracts_txs.py) grava a resposta bruta da
#   API Etherscan como JSON array, com os nomes de campo originais da API:
#     hash, blockNumber, timeStamp, from, to, gasUsed, ...
#   Este notebook lê sem schema forçado e depois renomeia/converte para o schema bronze.

from datetime import datetime, timezone
from pyspark.sql import functions as F

# ── Parâmetros ────────────────────────────────────────────────────────────────
catalog   = dbutils.widgets.get("catalog")
s3_bucket = dbutils.widgets.get("s3_bucket")
try:
    s3_prefix = dbutils.widgets.get("s3_prefix")
except Exception:
    s3_prefix = "batch"
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

# ── Ler JSON com schema inferido (campos originais da API Etherscan) ───────────
# O JSON tem campos: hash, blockNumber, timeStamp, from, to, value, gasUsed, input, ...
# NÃO usar schema forçado com nomes renomeados — Spark produziria NULLs.
try:
    df_etherscan = (
        spark.read
        .option("multiLine", "true")
        .json(s3_path)
    )
    count = df_etherscan.count()
except Exception as e:
    # Caminho não existe (hora sem transações) → não é erro
    print(f"[WARN] Nenhum dado encontrado em {s3_path}: {e}")
    count = 0

print(f"[INFO] {count} transações encontradas no S3")

if count == 0:
    print("[WARN] Sem dados — pulando carga Bronze")
else:
    # ── Mapear campos Etherscan → schema bronze ────────────────────────────────
    # Etherscan API → bronze table:
    #   hash         → tx_hash        (string)
    #   blockNumber  → block_number   (bigint)
    #   timeStamp    → timestamp      (timestamp, epoch seconds string)
    #   from         → from_address   (string; "from" é palavra reservada em SQL)
    #   to           → to_address     (string)
    #   value        → value          (string, wei)
    #   gasUsed      → gas_used       (bigint)
    #   input        → input          (string)
    # contract_address vem do nome do arquivo: txs_{addr}.json
    # ingestion_date derivado do exec_date

    ingestion_date = dt_end.date().isoformat()   # "2026-03-06"

    df_bronze = (
        df_etherscan
        # contract_address: extrair o endereço do nome do arquivo S3
        # Nota: input_file_name() não é suportado no Unity Catalog → usar _metadata.file_path
        .withColumn(
            "contract_address",
            F.regexp_extract(F.col("_metadata.file_path"), r"txs_(0x[^.]+)\.json", 1)
        )
        .withColumnRenamed("hash",        "tx_hash")
        .withColumn("block_number",  F.col("blockNumber").cast("bigint"))
        .withColumn(
            "timestamp",
            F.to_timestamp(F.col("timeStamp").cast("bigint"))
        )
        # "from" é palavra reservada em SQL, mas withColumnRenamed usa nome literal
        .withColumnRenamed("from",        "from_address")
        .withColumnRenamed("to",          "to_address")
        # value já é string (wei)
        .withColumn("gas_used",      F.col("gasUsed").cast("bigint"))
        # input já existe com nome correto
        .withColumn("ingestion_date", F.lit(ingestion_date).cast("date"))
        # Selecionar somente as colunas do schema bronze (descartar extras da API)
        .select(
            "contract_address",
            "tx_hash",
            "block_number",
            "timestamp",
            "from_address",
            "to_address",
            "value",
            "gas_used",
            "input",
            "ingestion_date",
        )
    )

    # ── Upsert em Bronze (idempotente por tx_hash) ─────────────────────────────
    # Limpar linhas com tx_hash NULL que possam ter sido inseridas com o schema errado
    spark.sql(f"""
        DELETE FROM `{catalog}`.b_ethereum.popular_contracts_txs
        WHERE tx_hash IS NULL
    """)
    # Deduplicate: a mesma tx_hash pode aparecer em múltiplos arquivos JSON
    # (se a tx envolve dois contratos rastreados). Delta MERGE exige unicidade na fonte.
    df_bronze = df_bronze.dropDuplicates(["tx_hash"])
    df_bronze.createOrReplaceTempView("staged_contracts_txs")

    spark.sql(f"""
        MERGE INTO `{catalog}`.b_ethereum.popular_contracts_txs AS tgt
        USING staged_contracts_txs AS src
        ON tgt.tx_hash = src.tx_hash
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

    print(f"[OK] {count} linhas mergeadas em `{catalog}`.b_ethereum.popular_contracts_txs")
