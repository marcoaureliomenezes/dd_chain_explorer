from pyspark.sql import SparkSession
from pyspark.sql.functions import col


def get_spark_session(app_name: str, master_url: str) -> SparkSession:
    spark = SparkSession.builder.appName(app_name).master(master_url).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


class BronzeToSilverAPIKeysConsume:

  def __init__(self, spark: SparkSession, bronze_table_name, silver_table_name: str):
    self.spark = spark
    self.bronze_table_name = bronze_table_name
    self.silver_table_name = silver_table_name


  def extract(self, data_ref, hour):
    df_app_logs_raw = (
    self.spark.table(self.bronze_table_name)
      .filter((col("dat_ref_carga") == data_ref) & (col('hour') == hour))
    )
    return df_app_logs_raw


  def transform(self, df_extracted):
    df_transformed = (
      df_extracted
    )
    return df_transformed

  # .filter(col("filename") == "2_mined_txs_crawler.py")
  # .withColumn("dat_ref_carga", concat_ws("-", col("year"), lpad(col("month"), 2, '0'), lpad(col("day"), 2, '0')))
  # .withColumnRenamed("logger", "job_name")
  # .select("level", "timestamp", "job_name", "filename", "message", "dat_ref_carga")

if __name__ == "__main__":
    

  SPARK_URL = "spark://spark-master:7077"
  APP_NAME = "BRONZE_TO_SILVER_API_KEY_CONSUMPTION"
  
  BRONZE_TABLE_NAME = "b_apps.app_logs"
  SILVER_TABLE_NAME = "s_apps.api_key_consumption"
  DATA = '2024-07-28'
  HORA = '02'

  spark = get_spark_session(APP_NAME, SPARK_URL)

  etl_engine = BronzeToSilverAPIKeysConsume(spark, BRONZE_TABLE_NAME, SILVER_TABLE_NAME)
  df_app_logs = etl_engine.extract(DATA, HORA)
  df_app_logs_transformed = etl_engine.transform(df_app_logs)
  df_app_logs_transformed.printSchema()
  df_app_logs_transformed.show()



  



