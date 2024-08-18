from pyspark.sql import SparkSession



class SparkUtils:

  @staticmethod
  def get_spark_session(app_name):
    spark = SparkSession.builder.appName(app_name).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
  

