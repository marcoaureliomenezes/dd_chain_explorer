import os
import pyspark

from logging import Logger
from pyspark.sql import SparkSession


class SparkUtils:

  @staticmethod
  def get_spark_session(logger: Logger, app_name: str) -> SparkSession:

    logger.info("Environment Variables:")
    logger.info(f"SPARK_MASTER: {os.getenv('SPARK_MASTER')}")
    logger.info(f"S3_URL: {os.getenv('S3_URL')}")
    logger.info(f"NESSIE_URI: {os.getenv('NESSIE_URI')}")
    logger.info(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID')[:4]}")
    logger.info(f"AWS_SECRET_ACCESS_KEY: {os.getenv('AWS_SECRET_ACCESS_KEY')[:4]}")
    
    conf = (
      pyspark.SparkConf()
      .setAppName(app_name)
      .set('spark.sql.catalog.nessie.s3.path-style-access', 'true')
      .set('spark.sql.catalog.nessie.warehouse', 's3a://lakehouse/warehouse')
      .set('spark.sql.catalog.nessie.cache-enabled', 'false')    
      .set('spark.hadoop.fs.s3a.access.key', os.getenv("AWS_ACCESS_KEY_ID"))
      .set('spark.hadoop.fs.s3a.secret.key', os.getenv("AWS_SECRET_ACCESS_KEY"))
      .set("spark.hadoop.fs.s3a.endpoint", os.getenv("S3_URL"))
      .set("spark.hadoop.fs.s3a.path.style.access", "true")
      .set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        
    )
    spark = SparkSession.builder.master(os.getenv("SPARK_MASTER")).config(conf=conf).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


  
  def glue_catalog_exists(self, catalog_name):
    os.getenv("AWS_REGION", "us-east-1")
    os.getenv("AWS_ACCESS_KEY_ID")
    os.getenv("AWS_SECRET_ACCESS_KEY")

    conf = (
      pyspark.SparkConf()
      .setAppName("GLUE_CATALOG_CHECK")
      .set("spark.jars_packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.8.0,org.apache.iceberg:iceberg-aws-bundle:1.8.0")
      .set("sparl.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
      .set("spark.sql.catalog.glue", "org.apache.iceberg.spark.SparkSessionCatalog")
      .set("spark.sql.catalog.glue.catalog-impl", "org.apache.iceberg.aws.glue.catalog.GlueCatalog")
      .set("spark.sql.catalog.warehouse", "s3a://lakehouse/warehouse")
      .set("spark.sql.catalog.glue.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    )
