import logging
import os

from datetime import datetime as dt, timedelta
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from hdfs import InsecureClient

from utils.etherscan import EthercanAPI
from utils.log_handlers import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.kafka_handlers import SchemaRegistryHandler

class ContractTransactionsCrawler:

  def __init__(self, logger, overwrite=True):
    self.logger = logger
    self.contract_address = None
    self.etherscan_client = None
    self.timestamp_interval = None
    self.basepath = None
    self.hdfs_client = None
    self.overwrite = overwrite
    self.configure_pagination()

  
  def config_contract_address(self, contract_address):
    self.contract_address = contract_address
    return self
  
  def config_etherscan_client(self, etherscan_client):
    self.etherscan_client = etherscan_client
    return self

  def config_hdfs_client(self, host):
    self.hdfs_client = InsecureClient(host)
    return self

  def config_timestamp_interval(self, end_date):
    end_date = dt.strptime(end_date, '%Y-%m-%d %H:%M:%S%z')
    start_date = end_date - timedelta(hours=1)
    start_timestamp, end_timestamp = int(start_date.timestamp()), int(end_date.timestamp())
    self.timestamp_interval = (start_timestamp, end_timestamp)
    self.logger.info(f"timestamp_start:{start_timestamp};timestamp_end:{end_timestamp}")
    return self

  def config_file_prefix(self, lake_path):
    assert self.timestamp_interval is not None, "Timestamp interval not configured"
    start_date = dt.fromtimestamp(self.timestamp_interval[0])
    partitioned_path = dt.strftime(start_date, 'year=%Y/month=%m/day=%d/hour=%H')
    basepath = f"{self.contract_address[:8]}/{partitioned_path}"
    self.basepath = {"local": f"./tmp/{basepath}", "hdfs": f"{lake_path}/{basepath}"}
    _ = os.makedirs(self.basepath["local"], exist_ok=True)
    _ = self.hdfs_client.makedirs(self.basepath["hdfs"])
    self.logger.info(f"local_path:{self.basepath['local']};lake_path:{self.basepath['hdfs']}")
    return self

  def configure_pagination(self, page=1, offset=100, sort='asc'):
    self.page = page
    self.offset = offset
    self.sort = sort
    return self

  def get_block_interval(self):
    get_block = lambda timestamp, closest: self.etherscan_client.get_block_by_timestamp(timestamp, closest=closest)
    block_before = get_block(self.timestamp_interval[0], closest='after')
    block_after = get_block(self.timestamp_interval[1], closest='before')
    if block_before["message"] != "OK" or block_after["message"] != "OK": return
    return block_before["result"], block_after["result"]

  def get_contract_tx_data(self, block_before, block_after):
    args = (self.contract_address, block_before, block_after, self.page, self.offset, self.sort)
    tx_data = self.etherscan_client.get_contract_tx_by_block_interval(*args)
    return tx_data
  
  def check_hdfs_file_exists(self, block_before):
    files_hdfs_path = self.hdfs_client.list(self.basepath['hdfs'])
    block_file = [file for file in files_hdfs_path if file.startswith(str(block_before))]
    if len(block_file) == 0: return
    return block_file[0] if len(block_file) > 0 else None

  def __get_transactions(self):
    data = []
    lower_limit, upper_limit = self.get_block_interval()
    block_before, block_after = lower_limit, upper_limit
    block_after = str(int(block_after) - 1)
    while block_before < block_after:
      if not self.overwrite: 
        hdfs_file_exists = self.check_hdfs_file_exists(block_before)
        if hdfs_file_exists:
          self.logger.info(f"file_exists:{hdfs_file_exists}")
          block_before = hdfs_file_exists.split("_")[-1].split(".")[0]
          if block_before != block_after:
            continue   
      result = self.get_contract_tx_data(block_before, block_after)
      if result["message"] != "OK":return
      if data == result["result"]: return
      else: data = result["result"]
      block_before = data[-1]["blockNumber"]
      yield data
      
  def __run_config_checks(self):
    assert self.etherscan_client is not None, "Etherscan client not configured"
    assert self.hdfs_client is not None, "HDFS client not configured"
    assert self.timestamp_interval is not None, "Timestamp interval not configured"
    assert self.contract_address is not None, "Contract address not configured"
    assert self.basepath is not None, "Basepath not configured"


  def __write_compressed_parquet(self, json_data, path):
    df_data = pd.DataFrame(json_data)
    table = pa.Table.from_pandas(df_data)
    pq.write_table(table, path, compression='SNAPPY')

  def run(self):
    self.__run_config_checks()
    for data in self.__get_transactions():
      start_block = data[0]["blockNumber"]
      end_block = data[-1]["blockNumber"]
      local_path = f"{self.basepath['local']}/{start_block}_{end_block}.parquet"
      hdfs_path = f"{self.basepath['hdfs']}/{start_block}_{end_block}.parquet"
      self.__write_compressed_parquet(data, local_path)
      self.hdfs_client.upload(hdfs_path, local_path, overwrite=True)
      self.logger.info(f"File uploaded to HDFS: {hdfs_path}")
  

if __name__ == "__main__":
  
  APP_NAME = "CONTRACT_TRANSACTIONS_CRAWLER"

  AKV_VAULT_NAME = os.getenv("AKV_VAULT_NAME")
  HOST_HDFS = os.getenv("HOST_HDFS")
  KAFKA_BROKERS = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  API_KEY_NAME = os.getenv("API_KEY_NAME")
  NETWORK = os.getenv("NETWORK")
  ADDRESS = os.getenv("ADDRESS", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
  END_DATE = os.getenv("END_DATE")
  LAKE_PATH = os.getenv("LAKE_PATH")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")

  print("Execution date: ", END_DATE)
  print("Type: ", type(END_DATE))

  akv_url = f'https://{AKV_VAULT_NAME}.vault.azure.net/'
  akv_client = SecretClient(vault_url=akv_url, credential=DefaultAzureCredential())
  
   
  logger = logging.getLogger(APP_NAME)
  logger.setLevel(logging.INFO)
  logger.addHandler(ConsoleLoggingHandler())

  schema_registry_handler = SchemaRegistryHandler(logger, SCHEMA_REGISTRY_URL)
  logs_schema = schema_registry_handler.get_avro_schema("schemas/application_logs_avro.json")
  producer_conf = {**KAFKA_BROKERS,  "client.id": APP_NAME, "acks": 1}
  logs_schema = schema_registry_handler.get_avro_schema("schemas/application_logs_avro.json")
  producer_logs = schema_registry_handler.create_avro_producer(producer_conf, logs_schema)
  kafka_handler = KafkaLoggingHandler(producer_logs, TOPIC_LOGS)
  logger.addHandler(kafka_handler)

  etherscan_client = EthercanAPI(logger, akv_client, API_KEY_NAME, NETWORK)

  crawler = (
    ContractTransactionsCrawler(logger, overwrite=True)
      .config_contract_address(ADDRESS)
      .config_etherscan_client(etherscan_client)
      .config_hdfs_client(HOST_HDFS)
      .config_timestamp_interval(END_DATE)
      .config_file_prefix(LAKE_PATH)
      .run()
  )
