from abc import ABC, abstractmethod
from utils.iceberg_utils import IcebergUtils
import json

class TableCreator:
    
    def __init__(self, logger, spark):
        self.logger = logger
        self.spark = spark

    def create_namespace(self, namespace):
      self.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {namespace}")
      self.logger.info(f"Namespace {namespace} created successfully!")
      self.spark.sql(f"SHOW NAMESPACES IN {namespace.split(".")[0]}").show()
      return

    def get_table_info(self, table_name):
      iceberg_utils = IcebergUtils(self.spark)
      self.spark.table(table_name).printSchema()
      iceberg_utils.print_iceberg_metadata(table_name)

    def get_iceberg_table_properties(self):
      properties = """
      TBLPROPERTIES (
        'gc.enabled' = 'true',
        'write.delete.mode' = 'copy-on-write',
        'write.update.mode' = 'merge-on-read',
        'write.merge.mode' = 'merge-on-read',
        'write.metadata.delete-after-commit.enabled' = 'true',
        'write.metadata.previous-versions-max' = '3',
        'write.parquet.compression-codec' = 'snappy'
      )
      """
      return properties
    
    