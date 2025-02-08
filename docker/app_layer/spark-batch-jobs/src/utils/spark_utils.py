import os
import pyspark

from pyspark.sql import SparkSession


class SparkUtils:

  @staticmethod
  def get_spark_session(app_name):

    print("Environment Variables:")
    print(os.getenv("S3_URL"))
    print(os.getenv("NESSIE_URI"))
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
    spark = SparkSession.builder.config(conf=conf).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


  