
from pyspark.sql.functions import col, monotonically_increasing_id


class IcebergUtils:

  def __init__(self, spark):
    self.spark = spark

  def get_specific_metadata(self, all_metadata, desired):
    tbl_properties = [i["data_type"] for i in all_metadata if i["col_name"] == desired][0]
    return tbl_properties

  def print_iceberg_metadata(self, table="nessie.learn.web_server_logs"):
    df_metadata = self.spark.sql(f"DESCRIBE EXTENDED {table}").filter(col("col_name") != "").withColumn("counter", monotonically_increasing_id())
    df_metadata.createOrReplaceTempView("df_metadata")
    threshold_bot_partition = "(SELECT counter FROM df_metadata WHERE col_name LIKE '# col_name')"
    threshold_top_partition = "(SELECT counter FROM df_metadata WHERE col_name LIKE '# Metadata Columns')"
    threshold_bot_properties = "(SELECT counter FROM df_metadata WHERE col_name LIKE '# Detailed Table%')"
    df_partitions = self.spark.sql(f"SELECT * FROM df_metadata WHERE counter > {threshold_bot_partition} AND counter < {threshold_top_partition}")
    df_properties = self.spark.sql(f"SELECT * FROM df_metadata WHERE counter > {threshold_bot_properties}").collect()
    important_props = ("Name", "Type", "Provider", "Location", "Table Properties")
    tbl_name, tbl_type, tbl_provider, tbl_location, tbl_properties = [self.get_specific_metadata(df_properties, metadata) for metadata in important_props]
    tbl_properties = {prop.split("=")[0]: prop.split("=")[1] for prop in tbl_properties.replace("]", "").replace("[", "").split(",")}
    print(f"Table Name: {tbl_name}\Table Type {tbl_type}\nTable Provider: {tbl_provider}\nTable Location: {tbl_location}")
    print("\nIceberg Table Properties:")
    for k, v in tbl_properties.items(): print(f"\t{k} => {v}")