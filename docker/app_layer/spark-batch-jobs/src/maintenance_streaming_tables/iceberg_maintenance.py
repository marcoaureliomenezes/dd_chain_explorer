from datetime import datetime as dt, timedelta

from functools import reduce


class IceStreamMaintainer:

  def __init__(self, logger, spark, table):
    self.logger = logger
    self.spark = spark
    self.table = table
  
  def rewrite_data_files(self, where=None):
    query = f"CALL nessie.system.rewrite_data_files(table => '{self.table}')"
    query_with_where = f"CALL nessie.system.rewrite_data_files(table => '{self.table}', where => '{where}')"
    self.logger.info(f"Rewriting data files for table {self.table}")
    self.logger.info(f"Query: {query}")
    if where is not None: self.spark.sql(query_with_where).show()
    else: self.spark.sql(query).show()

  def rewrite_manifests(self):
    query = f"CALL nessie.system.rewrite_manifests('{self.table}')"
    self.logger.info(f"Rewriting manifests for table {self.table}")
    self.logger.info(f"Query: {query}")
    self.spark.sql(query).show()

  def rewrite_position_delete_files(self):
    query = f"CALL nessie.system.rewrite_position_delete_files('{self.table}')"
    self.logger.info(f"Rewriting position delete files for table {self.table}")
    self.logger.info(f"Query: {query}")
    self.spark.sql(query).show()

  def expire_snapshots(self, hours_retained=24):
    timestamp_after_to_retain = dt.now() - timedelta(hours=hours_retained)
    query = f"CALL nessie.system.expire_snapshots('{self.table}', TIMESTAMP '{timestamp_after_to_retain}', 5)"
    self.logger.info(f"Expiring snapshots for table {self.table}")
    self.logger.info(f"Query: {query}")
    self.spark.sql(query).show()


  def remove_orphan_files(self):
    query = f"CALL nessie.system.remove_orphan_files(table => '{self.table}')"
    self.logger.info(f"Removing orphan files for table {self.table}")
    self.logger.info(f"Query: {query}")
    self.spark.sql(query).show()


