import os
import pyspark
from logging import Logger
from pyspark.sql import SparkSession


class SparkUtils:

  def get_spark_session(self, logger: Logger, app_name: str) -> SparkSession:
   
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
      .set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem"))
      
    spark = SparkSession.builder.config(conf=conf).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


  