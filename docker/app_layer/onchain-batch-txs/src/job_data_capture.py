import boto3
import logging
import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from datetime import datetime as dt, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from utils.etherscan import EthercanAPI
from utils.log_handlers import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.schema_registry_utils import SchemaRegistryUtils



class ContractTransactionsCrawler:

  def __init__(self, logger, etherscan_client, boto3_client, contract_address, overwrite=True):
    self.logger = logger
    self.etherscan_client = etherscan_client
    self.boto3_client = boto3_client
    self.contract_address = contract_address
    self.overwrite = overwrite
    self.timestamp_interval = None
    self.local_path = None
    self.s3_path = None
    self.configure_pagination()


  def configure_pagination(self, page=1, offset=100, sort='asc'):
    self.page = page
    self.offset = offset
    self.sort = sort
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
    self.basepath = {"local": f"./tmp/{basepath}", "s3": f"{lake_path}/{basepath}"}
    _ = os.makedirs(self.basepath["local"], exist_ok=True)
    self.logger.info(f"local_path:{self.basepath['local']};lake_path:{self.basepath['s3']}")
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
    assert self.s3 is not None, "S3 client not configured"
    assert self.timestamp_interval is not None, "Timestamp interval not configured"
    assert self.contract_address is not None, "Contract address not configured"
    assert self.basepath is not None, "Basepath not configured"


  def __write_compressed_parquet(self, json_data, path):
    df_data = pd.DataFrame(json_data)
    table = pa.Table.from_pandas(df_data)
    pq.write_table(table, path, compression='SNAPPY')


  

if __name__ == "__main__":
  
  APP_NAME = "CONTRACT_TRANSACTIONS_CRAWLER"
  TOPIC_LOGS = "etherscan.0.application.logs"
  KAFKA_BROKERS = os.getenv("KAFKA_BROKERS")
  SR_URL = os.getenv("SCHEMA_REGISTRY_URL")
  CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
  akv_url = f"https://{os.getenv('AKV_NAME')}.vault.azure.net/"
  akv_client = SecretClient(vault_url=akv_url, credential=DefaultAzureCredential())
   
  logger = logging.getLogger(APP_NAME)
  logger.setLevel(logging.INFO)
  sc_client = SchemaRegistryUtils.get_schema_registry_client(SR_URL)
  schema_registry_handler = SchemaRegistryUtils()
  logs_schema = schema_registry_handler.get_avro_schema(sc_client, f"{TOPIC_LOGS}-value")
  producer_conf = {"bootstrap.servers": KAFKA_BROKERS, "client.id": APP_NAME, "acks": 1}
  producer_logs = schema_registry_handler.create_avro_producer(producer_conf, logs_schema)
  kafka_handler = KafkaLoggingHandler(producer_logs, TOPIC_LOGS)
  logger.addHandler(kafka_handler)
  logger.addHandler(ConsoleLoggingHandler())


  boto3_client = boto3.client('s3',
      endpoint_url=os.getenv("S3_URL"),
      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

  etherscan_client = EthercanAPI(logger, akv_client, os.getenv("APK_NAME"), os.getenv("NETWORK"))

  crawler = (
    ContractTransactionsCrawler(
      logger,
      etherscan_client,
      boto3_client,
      contract_address=CONTRACT_ADDRESS,
      overwrite=True)
      .config_contract_address()
      .config_etherscan_client(etherscan_client)
      .config_timestamp_interval(os.getenv("END_DATE"))
      .config_file_prefix(os.getenv("S3_BUCKET"))
      .run()
  )
