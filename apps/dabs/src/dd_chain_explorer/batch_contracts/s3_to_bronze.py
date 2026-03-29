import argparse
import logging
from datetime import datetime

from pyspark.sql import SparkSession, functions as F

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw contract transactions from S3 into Bronze")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-prefix", default="batch")
    parser.add_argument("--exec-date", required=True, help="End of hourly window: YYYY-MM-DDTHH")
    args = parser.parse_args()

    catalog   = args.catalog
    s3_bucket = args.s3_bucket
    s3_prefix = args.s3_prefix
    exec_date = args.exec_date

    spark = SparkSession.builder.getOrCreate()

    # ── Derivar caminho S3 ─────────────────────────────────────────────────────────
    # O script Docker grava: {prefix}/year={Y}/month={M}/day={D}/hour={H}/txs_{addr}.json
    # usando datetime.fromtimestamp(end_timestamp) → sem zero-pad em month/day/hour
    dt_end = datetime.strptime(exec_date, "%Y-%m-%dT%H")
    s3_path = (
        f"s3://{s3_bucket}/{s3_prefix}"
        f"/year={dt_end.year}/month={dt_end.month}"
        f"/day={dt_end.day}/hour={dt_end.hour}/"
    )
    _log.info("Lendo S3: %s", s3_path)

    # ── Ler JSON com schema inferido (campos originais da API Etherscan) ───────────
    try:
        df_etherscan = (
            spark.read
            .option("multiLine", "true")
            .json(s3_path)
        )
        count = df_etherscan.count()
    except Exception as e:
        # Caminho não existe (hora sem transações) → não é erro
        _log.warning("Nenhum dado encontrado em %s: %s", s3_path, e)
        count = 0

    _log.info("%d transações encontradas no S3", count)

    if count == 0:
        _log.warning("Sem dados — pulando carga Bronze")
        return

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
    # contract_address: extraído do nome do arquivo via _metadata.file_path
    # ingestion_date: derivado do exec_date

    ingestion_date = dt_end.date().isoformat()  # "2026-03-06"

    df_bronze = (
        df_etherscan
        # contract_address: input_file_name() não é suportado no Unity Catalog → usar _metadata.file_path
        .withColumn(
            "contract_address",
            F.regexp_extract(F.col("_metadata.file_path"), r"txs_(0x[^.]+)\.json", 1),
        )
        .withColumnRenamed("hash",    "tx_hash")
        .withColumn("block_number",   F.col("blockNumber").cast("bigint"))
        .withColumn("timestamp",      F.to_timestamp(F.col("timeStamp").cast("bigint")))
        .withColumnRenamed("from",    "from_address")
        .withColumnRenamed("to",      "to_address")
        .withColumn("gas_used",       F.col("gasUsed").cast("bigint"))
        .withColumn("ingestion_date", F.lit(ingestion_date).cast("date"))
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
    spark.sql(f"""
        DELETE FROM `{catalog}`.b_ethereum.popular_contracts_txs
        WHERE tx_hash IS NULL
    """)
    df_bronze = df_bronze.dropDuplicates(["tx_hash"])
    df_bronze.createOrReplaceTempView("staged_contracts_txs")

    spark.sql(f"""
        MERGE INTO `{catalog}`.b_ethereum.popular_contracts_txs AS tgt
        USING staged_contracts_txs AS src
        ON tgt.tx_hash = src.tx_hash
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

    _log.info("%d linhas mergeadas em `%s`.b_ethereum.popular_contracts_txs", count, catalog)


if __name__ == "__main__":
    main()
