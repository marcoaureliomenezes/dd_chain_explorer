"""dm-delta-maintenance — optimize_bronze task.

Delta Lake maintenance: optimize, vacuum, and monitor all tables

Usage (local):
    python -m dm_delta_maintenance.optimize_bronze \\
        --catalog dev \\
        --storage-mode managed

Usage (Databricks wheel task):
    entry_point: dm-delta-maintenance-optimize-bronze
"""

from __future__ import annotations

import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class Optimizebronze:
    """Main logic for the optimize_bronze task."""

    BRONZE_TABLES = [
        ("b_ethereum", "b_blocks_data",          "number"),
        ("b_ethereum", "b_transactions_data",    "blockNumber"),
        ("b_ethereum", "b_transactions_decoded", "tx_hash"),
        ("b_app_logs", "b_app_logs_data",        "logger"),
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
        """Optimize all Bronze tables."""
        _log.info(
            "Running optimize_bronze | catalog=%s | storage_mode=%s",
            self.catalog, self.storage_mode,
        )
        for schema, table, zorder_col in self.BRONZE_TABLES:
            full = f"`{self.catalog}`.{schema}.{table}"
            _log.info("Optimizing %s ...", full)
            try:
                self.spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
                _log.info("Optimized %s", full)
            except Exception as exc:
                _log.warning("Could not optimize %s: %s", full, exc)
        _log.info("optimize_bronze completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="dm-delta-maintenance — optimize_bronze")
    parser.add_argument("--catalog",         required=True, help="Unity Catalog name")
    parser.add_argument("--storage-mode",    default="managed", choices=["managed", "external"],
                        help="Table storage mode: managed (DEV/HML) or external (PROD)")
    parser.add_argument("--lakehouse-bucket", default="", help="S3 bucket for EXTERNAL tables (PROD only)")
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    Optimizebronze(
        spark=spark,
        catalog=args.catalog,
        storage_mode=args.storage_mode,
        lakehouse_bucket=args.lakehouse_bucket,
    ).run()


if __name__ == "__main__":
    main()
