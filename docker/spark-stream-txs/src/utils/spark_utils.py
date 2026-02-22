import os
import logging

from logging import Logger
from pyspark.sql import SparkSession


class SparkUtils:

    @staticmethod
    def get_spark_session(logger: Logger, app_name: str) -> SparkSession:
        spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
        logger.info(f"Starting Spark session: app={app_name}, master={spark_master}")
        spark = (
            SparkSession.builder
            .master(spark_master)
            .appName(app_name)
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("ERROR")
        return spark
