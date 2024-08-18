from pyspark.sql import SparkSession

def get_spark_session(app_name: str, master_url: str) -> SparkSession:
  spark = SparkSession.builder.appName(app_name).master(master_url).getOrCreate()
  spark.sparkContext.setLogLevel("ERROR")
  return spark