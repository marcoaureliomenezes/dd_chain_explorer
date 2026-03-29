import argparse
import logging
from datetime import datetime

from pyspark.sql import SparkSession, functions as F

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform Bronze contract txs into Silver")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--exec-date", required=True, help="End of hourly window: YYYY-MM-DDTHH")
    args = parser.parse_args()

    catalog   = args.catalog
    exec_date = args.exec_date

    spark = SparkSession.builder.getOrCreate()

    dt_end = datetime.strptime(exec_date, "%Y-%m-%dT%H")
    ingestion_date = dt_end.strftime("%Y-%m-%d")

    _log.info("Processando Bronze → Silver para ingestion_date = %s", ingestion_date)

    # ── Ler Bronze filtrado por data ───────────────────────────────────────────────
    df_bronze = (
        spark.table(f"`{catalog}`.b_ethereum.popular_contracts_txs")
        .filter(F.col("ingestion_date") == F.lit(ingestion_date).cast("date"))
    )

    count = df_bronze.count()
    _log.info("%d linhas Bronze para data %s", count, ingestion_date)

    if count == 0:
        _log.warning("Bronze vazio para esta data — pulando Silver")
        return

    # ── Transformação ──────────────────────────────────────────────────────────
    # Deduplicate: a mesma tx_hash pode aparecer em várias listas de contratos.
    df_bronze = df_bronze.dropDuplicates(["tx_hash"])

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

    _log.info("%d linhas mergeadas em `%s`.s_apps.transactions_batch", count, catalog)

    total = spark.table(f"`{catalog}`.s_apps.transactions_batch").count()
    _log.info("Total em s_apps.transactions_batch: %d linhas", total)


if __name__ == "__main__":
    main()
