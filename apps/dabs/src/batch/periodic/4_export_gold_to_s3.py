import argparse
import logging

from pyspark.sql import SparkSession, functions as F

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class GoldExporter:
    def __init__(self, spark: SparkSession, catalog: str, s3_path: str) -> None:
        self.spark = spark
        self.catalog = catalog
        self.s3_path = s3_path

    def export_api_key_consumption(self) -> None:
        cat = self.catalog
        df_etherscan = (
            self.spark.table(f"`{cat}`.g_api_keys.etherscan_consumption")
            .withColumn("source", F.lit("etherscan"))
        )
        df_web3 = (
            self.spark.table(f"`{cat}`.g_api_keys.web3_keys_consumption")
            .withColumn("source", F.lit("web3"))
        )
        df_combined = df_etherscan.unionByName(df_web3, allowMissingColumns=True)

        count = df_combined.count()
        _log.info("Exporting %d rows to S3", count)

        (
            df_combined.coalesce(1)
            .write
            .mode("overwrite")
            .json(f"{self.s3_path}/gold_api_keys")
        )
        _log.info("Gold API key consumption exported to %s/gold_api_keys", self.s3_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Gold API key consumption views to S3")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--export-s3-path", required=True)
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    GoldExporter(spark, args.catalog, args.export_s3_path).export_api_key_consumption()


if __name__ == "__main__":
    main()
