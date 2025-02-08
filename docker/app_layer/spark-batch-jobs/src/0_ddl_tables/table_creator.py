from abc import ABC, abstractmethod
from iceberg_utils import IcebergUtils


class TableCreator(ABC):
    
    def __init__(self, spark, table_name):
        self.spark = spark
        self.table_name = table_name

    def create_namespace(self):
      namespace = ".".join(self.table_name.split(".")[:2])
      self.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {namespace}")
      print(f"Namespace {namespace} created successfully!")
      self.spark.sql(f"SHOW NAMESPACES IN {namespace.split(".")[0]}").show()
      return

    def get_table_info(self):
      iceberg_utils = IcebergUtils(self.spark)
      self.spark.table(self.table_name).printSchema()
      iceberg_utils.print_iceberg_metadata(self.table_name)


    @abstractmethod
    def create_table(self):
        pass
