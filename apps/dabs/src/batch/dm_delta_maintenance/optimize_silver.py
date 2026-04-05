"""dm-delta-maintenance — optimize_silver task.

Delta Lake maintenance: optimize, vacuum, and monitor all tables

Usage (local):
    python -m dm_delta_maintenance.optimize_silver \\
        --catalog dev \\
        --storage-mode managed

Usage (Databricks wheel task):
    entry_point: dm-delta-maintenance-optimize-silver
"""

from __future__ import annotations

import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class Optimizesilver:
    """Main logic for the optimize_silver task."""

    SILVER_TABLES = [
        ("s_apps", "blocks_fast",               "block_number"),
        ("s_apps", "blocks_withdrawals",        "block_number"),
        ("s_apps", "transactions_fast",         "block_number"),
        ("s_apps", "transactions_ethereum",     "block_number"),
        ("s_apps", "txs_inputs_decoded_fast",   "tx_hash"),
        ("s_logs", "logs_streaming",            "event_time"),
        ("s_logs", "logs_batch",                "event_time"),
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
        """Optimize all Silver tables."""
        _log.info(
            "Running optimize_silver | catalog=%s | storage_mode=%s",
            self.catalog, self.storage_mode,
        )
        for schema, table, zorder_col in self.SILVER_TABLES:
            full = f"`{self.catalog}`.{schema}.{table}"
            _log.info("Optimizing %s ...", full)
            try:
                self.spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
                _log.info("Optimized %s", full)
            except Exception as exc:
                _log.warning("Could not optimize %s: %s", full, exc)
        _log.info("optimize_silver completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="dm-delta-maintenance — optimize_silver")
    parser.add_argument("--catalog",         required=True, help="Unity Catalog name")
    parser.add_argument("--storage-mode",    default="managed", choices=["managed", "external"],
                        help="Table storage mode: managed (DEV/HML) or external (PROD)")
    parser.add_argument("--lakehouse-bucket", default="", help="S3 bucket for EXTERNAL tables (PROD only)")
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    Optimizesilver(
        spark=spark,
        catalog=args.catalog,
        storage_mode=args.storage_mode,
        lakehouse_bucket=args.lakehouse_bucket,
    ).run()


if __name__ == "__main__":
    main()
