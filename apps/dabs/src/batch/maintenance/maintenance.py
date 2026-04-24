import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class DeltaMaintenance:
    BRONZE_TABLES = [
        ("b_ethereum", "b_blocks_data",          "number"),
        ("b_ethereum", "b_transactions_data",    "blockNumber"),
        ("b_ethereum", "b_transactions_decoded", "tx_hash"),
        ("b_app_logs", "b_app_logs_data",        "logger"),
    ]

    SILVER_TABLES = [
        ("s_apps", "blocks_fast",               "block_number"),
        ("s_apps", "blocks_withdrawals",        "block_number"),
        ("s_apps", "transactions_fast",         "block_number"),
        ("s_apps", "transactions_ethereum",     "block_number"),
        ("s_apps", "canonical_blocks_index",    "block_number"),
        ("s_apps", "txs_inputs_decoded_fast",   "tx_hash"),
        ("s_logs", "logs_streaming",            "event_time"),
        ("s_logs", "logs_batch",                "event_time"),
    ]

    GOLD_TABLES = [
        ("g_apps",      "popular_contracts_ranking", "tx_count"),
        ("g_apps",      "peer_to_peer_txs",          "block_number"),
        ("g_apps",      "ethereum_gas_consume",      "block_number"),
        ("g_apps",      "transactions_lambda",       "block_number"),
        ("g_api_keys",  "etherscan_consumption",     "api_key_name"),
        ("g_api_keys",  "web3_keys_consumption",     "api_key_name"),
        ("g_network",   "network_metrics_hourly",    "hour_bucket"),
    ]

    ALL_TABLES = [
        "b_ethereum.b_blocks_data",
        "b_ethereum.b_transactions_data",
        "b_ethereum.b_transactions_decoded",
        "b_app_logs.b_app_logs_data",
        "s_apps.blocks_fast",
        "s_apps.blocks_withdrawals",
        "s_apps.transactions_fast",
        "s_apps.transactions_ethereum",
        "s_apps.txs_inputs_decoded_fast",
        "s_logs.logs_streaming",
        "s_logs.logs_batch",
        "g_apps.popular_contracts_ranking",
        "g_apps.peer_to_peer_txs",
        "g_apps.ethereum_gas_consume",
        "g_apps.transactions_lambda",
        "g_api_keys.etherscan_consumption",
        "g_api_keys.web3_keys_consumption",
        "g_network.network_metrics_hourly",
    ]

    def __init__(self, spark: SparkSession, catalog: str) -> None:
        self.spark = spark
        self.catalog = catalog

    def optimize_bronze(self) -> None:
        for schema, table, zorder_col in self.BRONZE_TABLES:
            full = f"`{self.catalog}`.{schema}.{table}"
            _log.info("Optimizing %s ...", full)
            try:
                self.spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
                _log.info("Optimized %s", full)
            except Exception as exc:
                _log.warning("Could not optimize %s: %s", full, exc)

    def optimize_silver(self) -> None:
        for schema, table, zorder_col in self.SILVER_TABLES:
            full = f"`{self.catalog}`.{schema}.{table}"
            _log.info("Optimizing %s ...", full)
            try:
                self.spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
                _log.info("Optimized %s", full)
            except Exception as exc:
                _log.warning("Could not optimize %s: %s", full, exc)

    def optimize_gold(self) -> None:
        for schema, table, zorder_col in self.GOLD_TABLES:
            full = f"`{self.catalog}`.{schema}.{table}"
            _log.info("Optimizing %s ...", full)
            try:
                self.spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
                _log.info("Optimized %s", full)
            except Exception as exc:
                _log.warning("Could not optimize %s: %s", full, exc)

    def vacuum(self, retention_hours: int = 168) -> None:
        for t in self.ALL_TABLES:
            full = f"`{self.catalog}`.{t}"
            _log.info("VACUUM %s RETAIN %d HOURS ...", full, retention_hours)
            try:
                self.spark.sql(f"VACUUM {full} RETAIN {retention_hours} HOURS")
                _log.info("Vacuumed %s", full)
            except Exception as exc:
                _log.warning("Could not vacuum %s: %s", full, exc)

    def monitor(self) -> None:
        metrics = []
        for t in self.ALL_TABLES:
            full = f"`{self.catalog}`.{t}"
            try:
                count  = self.spark.table(full).count()
                detail = self.spark.sql(f"DESCRIBE DETAIL {full}").collect()[0]
                metrics.append({
                    "table":         t,
                    "row_count":     count,
                    "num_files":     detail["numFiles"],
                    "size_bytes":    detail["sizeInBytes"],
                    "last_modified": str(detail["lastModified"]),
                })
                _log.info(
                    "%s: %d rows | %d files | %d bytes",
                    t, count, detail["numFiles"], detail["sizeInBytes"],
                )
            except Exception as exc:
                _log.warning("Could not query %s: %s", t, exc)

        if metrics:
            self.spark.createDataFrame(metrics).show(truncate=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Delta table maintenance for DD Chain Explorer")
    parser.add_argument("--catalog", required=True)
    parser.add_argument(
        "--step",
        required=True,
        choices=["optimize-bronze", "optimize-silver", "optimize-gold", "vacuum", "monitor"],
    )
    parser.add_argument("--retention-hours", type=int, default=168)
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    maint = DeltaMaintenance(spark, args.catalog)

    if args.step == "optimize-bronze":
        maint.optimize_bronze()
    elif args.step == "optimize-silver":
        maint.optimize_silver()
    elif args.step == "optimize-gold":
        maint.optimize_gold()
    elif args.step == "vacuum":
        maint.vacuum(args.retention_hours)
    elif args.step == "monitor":
        maint.monitor()


if __name__ == "__main__":
    main()
