import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class DeltaMaintenance:
    BRONZE_TABLES = [
        ("b_ethereum", "popular_contracts_txs", "contract_address"),
    ]

    SILVER_TABLES = [
        ("s_apps", "transactions_fast",         "block_number"),
        ("s_apps", "blocks_fast",               "event_time"),
        ("s_apps", "transactions_batch",        "block_number"),
        ("s_apps", "popular_contracts_ranking", "contract_address"),
        ("s_apps", "transactions_lambda",       "contract_address"),
        ("s_logs", "logs_streaming",            "job_name"),
        ("s_logs", "logs_batch",                "job_name"),
    ]

    ALL_TABLES = [
        "b_ethereum.popular_contracts_txs",
        "s_apps.transactions_fast",
        "s_apps.blocks_fast",
        "s_apps.transactions_batch",
        "s_apps.popular_contracts_ranking",
        "s_apps.transactions_lambda",
        "s_logs.logs_streaming",
        "s_logs.logs_batch",
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
        choices=["optimize-bronze", "optimize-silver", "vacuum", "monitor"],
    )
    parser.add_argument("--retention-hours", type=int, default=168)
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    maint = DeltaMaintenance(spark, args.catalog)

    if args.step == "optimize-bronze":
        maint.optimize_bronze()
    elif args.step == "optimize-silver":
        maint.optimize_silver()
    elif args.step == "vacuum":
        maint.vacuum(args.retention_hours)
    elif args.step == "monitor":
        maint.monitor()


if __name__ == "__main__":
    main()
