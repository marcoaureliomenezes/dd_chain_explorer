"""dm-delta-maintenance — optimize_gold task.

Delta Lake maintenance: optimize, vacuum, and monitor all tables

Usage (local):
    python -m dm_delta_maintenance.optimize_gold \\
        --catalog dev \\
        --storage-mode managed

Usage (Databricks wheel task):
    entry_point: dm-delta-maintenance-optimize-gold
"""

from __future__ import annotations

import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class Optimizegold:
    """Main logic for the optimize_gold task."""

    GOLD_TABLES = [
        # g_apps
        ("g_apps",      "popular_contracts_ranking",      "tx_count"),
        ("g_apps",      "peer_to_peer_txs",               "block_number"),
        ("g_apps",      "ethereum_gas_consume",           "block_number"),
        ("g_apps",      "transactions_lambda",            "block_number"),
        ("g_apps",      "gas_price_distribution_hourly",  "hour_bucket"),
        ("g_apps",      "p2p_transfer_metrics_hourly",    "hour_bucket"),
        ("g_apps",      "contract_method_activity",       "hour_bucket"),
        ("g_apps",      "contract_deploy_metrics_hourly", "hour_bucket"),
        ("g_apps",      "contract_volume_ranking",        "call_count"),
        # g_network
        ("g_network",   "network_metrics_hourly",         "hour_bucket"),
        ("g_network",   "eth_burn_hourly",                "hour_bucket"),
        ("g_network",   "validator_activity",             "blocks_produced"),
        ("g_network",   "chain_health_metrics",           "hour_bucket"),
        ("g_network",   "withdrawal_metrics",             "hour_bucket"),
        ("g_network",   "block_production_health",        "hour_bucket"),
        # g_api_keys
        ("g_api_keys",  "etherscan_consumption",          "api_key_name"),
        ("g_api_keys",  "web3_keys_consumption",          "api_key_name"),
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
        """Optimize all Gold tables."""
        _log.info(
            "Running optimize_gold | catalog=%s | storage_mode=%s",
            self.catalog, self.storage_mode,
        )
        for schema, table, zorder_col in self.GOLD_TABLES:
            full = f"`{self.catalog}`.{schema}.{table}"
            _log.info("Optimizing %s ...", full)
            try:
                self.spark.sql(f"OPTIMIZE {full} ZORDER BY ({zorder_col})")
                _log.info("Optimized %s", full)
            except Exception as exc:
                _log.warning("Could not optimize %s: %s", full, exc)
        _log.info("optimize_gold completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="dm-delta-maintenance — optimize_gold")
    parser.add_argument("--catalog",         required=True, help="Unity Catalog name")
    parser.add_argument("--storage-mode",    default="managed", choices=["managed", "external"],
                        help="Table storage mode: managed (DEV/HML) or external (PROD)")
    parser.add_argument("--lakehouse-bucket", default="", help="S3 bucket for EXTERNAL tables (PROD only)")
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    Optimizegold(
        spark=spark,
        catalog=args.catalog,
        storage_mode=args.storage_mode,
        lakehouse_bucket=args.lakehouse_bucket,
    ).run()


if __name__ == "__main__":
    main()
