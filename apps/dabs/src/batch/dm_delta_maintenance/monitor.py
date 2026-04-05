"""dm-delta-maintenance — monitor task.

Delta Lake maintenance: optimize, vacuum, and monitor all tables

Usage (local):
    python -m dm_delta_maintenance.monitor \\
        --catalog dev \\
        --storage-mode managed

Usage (Databricks wheel task):
    entry_point: dm-delta-maintenance-monitor
"""

from __future__ import annotations

import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class Monitor:
    """Main logic for the monitor task."""

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

    def __init__(
        self,
        spark: SparkSession,
        catalog: str,
        storage_mode: str = "managed",
        lakehouse_bucket: str = "",
    ) -> None:
        self.spark = spark
        self.catalog = catalog
        self.storage_mode = storage_mode
        self.lakehouse_bucket = lakehouse_bucket

    def _table(self, schema: str, name: str) -> str:
        return f"`{self.catalog}`.{schema}.{name}"

    def _location(self, relative_path: str) -> str:
        """Returns LOCATION clause for EXTERNAL tables (PROD only)."""
        if self.storage_mode == "external" and self.lakehouse_bucket:
            return f"LOCATION 's3://{self.lakehouse_bucket}/{relative_path}'"
        return ""

    def run(self) -> None:
        """Collect and display table metrics."""
        _log.info(
            "Running monitor | catalog=%s | storage_mode=%s",
            self.catalog, self.storage_mode,
        )
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
        _log.info("monitor completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="dm-delta-maintenance — monitor")
    parser.add_argument("--catalog",         required=True, help="Unity Catalog name")
    parser.add_argument("--storage-mode",    default="managed", choices=["managed", "external"],
                        help="Table storage mode: managed (DEV/HML) or external (PROD)")
    parser.add_argument("--lakehouse-bucket", default="", help="S3 bucket for EXTERNAL tables (PROD only)")
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    Monitor(
        spark=spark,
        catalog=args.catalog,
        storage_mode=args.storage_mode,
        lakehouse_bucket=args.lakehouse_bucket,
    ).run()


if __name__ == "__main__":
    main()
