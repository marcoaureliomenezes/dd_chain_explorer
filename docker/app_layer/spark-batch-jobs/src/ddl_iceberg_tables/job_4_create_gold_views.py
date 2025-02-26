import logging
from pyspark.sql import SparkSession
from logging import Logger

from utils.spark_utils import SparkUtils
from dm_33_utils.logger_utils import ConsoleLoggingHandler


class GoldViewsCreator:

  def __init__(self, logger: Logger, spark: SparkSession):
      self.logger = logger
      self.spark = spark
      
  def create_namespace(self, nm_name: str) -> None:
    self.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {nm_name}").show()
    self.logger.info(f"Namespace {nm_name} created")

    
  def create_view_popular_contracts(self, view_name: str, days: int=1) -> None:
    source_table = "nessie.s_apps.transactions_fast"
    query = f"""
    CREATE OR REPLACE VIEW {view_name} AS
    SELECT 
      to_address AS contract_address, 
      COUNT(*) AS num_transactions, 
      MIN(dat_ref) AS start_date,
      MAX(dat_ref) AS end_date
    FROM {source_table}
    WHERE transaction_type = 'CONTRACT_CALL' 
    AND dat_ref >= DATE_SUB(CURRENT_DATE(), {days}) 
    GROUP BY to_address
    ORDER BY num_transactions DESC"""
    self.spark.sql(query)
    self.logger.info(f"View {view_name} created successfully")
    return

  def create_view_latest_data(self, view_name: str) -> None:
    query = f"""
    CREATE OR REPLACE VIEW {view_name} AS
    SELECT 
      (SELECT MAX(ingestion_time) FROM nessie.b_fast.kafka_topics_multiplexed) newst_kafka_topics_multiplexed,
      (SELECT MAX(ingestion_time) FROM nessie.s_apps.mined_blocks_events) newst_mined_blocks_events,
      (SELECT MAX(ingestion_time) FROM nessie.s_apps.blocks_fast) newst_blocks_fast,
      (SELECT MAX(ingestion_time) FROM nessie.s_apps.blocks_txs_fast) newst_blocks_txs_fast,
      (SELECT MAX(ingestion_time) FROM nessie.s_apps.transactions_fast) newst_transactions_fast,
      (SELECT MAX(ingestion_time) FROM nessie.s_logs.apps_logs_fast) newst_apps_logs_fast"""
    self.spark.sql(query)
    self.logger.info(f"View {view_name} created successfully")
    return
  

  def create_view_api_keys_usage(self, view_name: str) -> None:
    query = f"""
    CREATE OR REPLACE VIEW {view_name} AS
    SELECT SUBSTRING(message, 13, 36) AS api_key, COUNT(*) AS num_requests, dat_ref
    FROM nessie.s_logs.apps_logs_fast WHERE message LIKE 'API_request%'
    GROUP BY api_key, dat_ref
    ORDER BY dat_ref, num_requests DESC
    """
    self.spark.sql(query).show()
    self.logger.info(f"View {view_name} created successfully")


if __name__ == "__main__":

  APP_NAME = "CREATE_SILVER_FAST_LOGS_TABLES"
  VIEW_GOLD_POP_CONTRACTS_1D = "g_chain.popular_contracts_1d"
  VIEW_GOLD_POP_CONTRACTS_7D = "g_chain.popular_contracts_7d"
  VIEW_FRESH_DATA = "g_bench.latest_data"
  VIEW_API_KEYS_USAGE = "g_bench.api_keys_usage"

  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  spark = SparkUtils().get_spark_session(LOGGER, APP_NAME)
  views_creator = GoldViewsCreator(LOGGER, spark)
  views_creator.create_namespace("g_chain")
  views_creator.create_namespace("g_bench")

  # CRIA VIEW 1
  views_creator.create_view_popular_contracts(VIEW_GOLD_POP_CONTRACTS_1D, 1)

  # CRIA VIEW 2
  views_creator.create_view_popular_contracts(VIEW_GOLD_POP_CONTRACTS_7D, 7)

  # CRIA VIEW 3
  views_creator.create_view_latest_data(VIEW_FRESH_DATA)

  # CRIA VIEW 4
  views_creator.create_view_api_keys_usage(VIEW_API_KEYS_USAGE)
  spark.stop()
  LOGGER.info("All views created successfully")




