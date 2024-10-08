import pyspark
from pyspark.sql import SparkSession
import os



def get_spark_session(app_name):

  MASTER = "spark://spark-master:7077"
  jar_packages = [
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1",
    "org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:0.95.0",
    "software.amazon.awssdk:bundle:2.17.178",
    "software.amazon.awssdk:url-connection-client:2.17.178",
    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
    "org.apache.spark:spark-avro_2.12:3.5.1"
  ]

  spark_extensions = [
    "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "org.projectnessie.spark.extensions.NessieSparkSessionExtensions"
  ]

  print("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
  print(os.getenv("S3_URL"))
  print(os.getenv("NESSIE_URI"))
  print(os.getenv("AWS_ACCESS_KEY_ID"))
  print(os.getenv("AWS_SECRET_ACCESS_KEY"))
    
  conf = (
      pyspark.SparkConf()
      .setAppName(app_name)
      .set('spark.jars.packages', ','.join(jar_packages))
      .set('spark.sql.extensions', ','.join(spark_extensions))
      .set('spark.sql.catalog.nessie', "org.apache.iceberg.spark.SparkCatalog")
      .set('spark.sql.catalog.nessie.uri', os.getenv("NESSIE_URI"))
      .set('spark.sql.catalog.nessie.ref', 'main')
      .set('spark.sql.catalog.nessie.authentication.type', 'NONE')
      .set("spark.executor.cores", "1")
      .set("spark.executor.memory", "512M")
      
      .set('spark.sql.catalog.nessie.catalog-impl', 'org.apache.iceberg.nessie.NessieCatalog')
      .set('spark.sql.catalog.nessie.io-impl', 'org.apache.iceberg.aws.s3.S3FileIO')
      .set('spark.sql.catalog.nessie.s3.endpoint', os.getenv("S3_URL"))
      .set('spark.sql.catalog.nessie.warehouse', 's3a://warehouse')
      .set('spark.hadoop.fs.s3a.access.key', os.getenv("AWS_ACCESS_KEY_ID"))
      .set('spark.hadoop.fs.s3a.secret.key', os.getenv("AWS_SECRET_ACCESS_KEY"))
      .set("spark.hadoop.fs.s3a.endpoint", os.getenv("S3_URL"))
      .set("spark.hadoop.fs.s3a.path.style.access", "true")
      .set("spark.hadoop.fs.s3a.endpoint.region", "")
      .set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )

  spark = SparkSession.builder.config(conf=conf).master(MASTER).getOrCreate()
  spark.sparkContext.setLogLevel("ERROR")
  return spark

    