import glob
import json
import logging
import os
import sys
import time
import subprocess

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from utils.etherscan import EthercanAPI
from utils.dm_data_handler import DMDataHandler
from utils.dm_logger import ConsoleLoggingHandler, KafkaLoggingHandler


class ContractTransactionsCrawler:

  def __init__(self, logger, api_key, network, timestamp_before, timestamp_after):
    self.logger = logger
    self.etherscan = EthercanAPI(api_key, network)
    self.timestamp_before = timestamp_before
    self.timestamp_after = timestamp_after


  def write_data_to_file_wal(self, data, contract_address):
    block_interval = (data[0]["blockNumber"], data[-1]["blockNumber"])
    base_path = f"./tmp/{self.timestamp_before}_{self.timestamp_after}/{contract_address}"
    print(f"Base path: {base_path}")
    # self.logger.info(f"Writing data to file: {filepath}")
    # return filepath

  def get_latest_block_by_filenames(self, contract_address):
    path_to_read = f"./tmp/{self.timestamp_before}_{self.timestamp_after}/{contract_address}/*"
    file_names = [file.split("/")[-1] for file in glob.glob(path_to_read)]
    block_after = [int(file.split("_")[-1].split(".")[0]) for file in file_names]
    if len(block_after) == 0: return 0
    return str(max(block_after))


  def get_raw_transactions(self, address, lower_limit, upper_limit):
    
    while lower_limit < upper_limit:
      result = self.etherscan.get_contract_transactions_by_block_interval(address, lower_limit, upper_limit, page=1, offset=100, sort='asc')
      if result["message"] != "OK": return
      else: data = result["result"]
      yield data
      lower_limit = data[-1]["blockNumber"]
      time.sleep(1)
    if lower_limit == upper_limit:
      return True
    

  def get_transactions(self, address, block_before, block_after):
    lower_limit = block_before
    upper_limit = block_after
    data = []
    for data in self.get_raw_transactions(address, lower_limit, upper_limit):
      yield data
      

  def get_block_interval(self):
    block_before = self.etherscan.get_block_by_timestamp(self.timestamp_before, closest='after')
    block_after = self.etherscan.get_block_by_timestamp(self.timestamp_after, closest='before')
    print("Block 1: ", block_before)
    print("Block 2: ", block_after)
    if block_before["message"] != "OK" or block_after["message"] != "OK": return
    return block_before["result"], block_after["result"]



def main(network, address, akv_name, api_key_name, **kwargs):

  APP_NAME = "CONTRACT_TRANSACTIONS_CRAWLER"
  AKV_URL = f'https://{akv_name}.vault.azure.net/'
  AKV_CLIENT = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())
  API_KEY = AKV_CLIENT.get_secret(api_key_name).value
  
  # Configurando Logging para console e Kafka
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)

  # ConsoleLoggingHandler = ConsoleLoggingHandler()
  # LOGGER.addHandler(ConsoleLoggingHandler)
  
  #kafka_handler = KafkaLoggingHandler(PRODUCER_LOGS, TOPIC_LOGS)
  #LOGGER.addHandler(kafka_handler)

  start_timestamp = 1722291913
  end_timestamp = 1722297513
  crawler = ContractTransactionsCrawler(LOGGER, API_KEY, network, start_timestamp, end_timestamp)

  block_before, block_after = crawler.get_block_interval()
  data_transaction_generator = crawler.get_transactions(address, block_before, block_after)
  
  
  dm_data_handler = DMDataHandler(LOGGER)

  for data in data_transaction_generator:

    block_before = data[0]["blockNumber"]
    block_after = data[-1]["blockNumber"]

    data_str = json.dumps(data)
    
    data_encrypted, key = dm_data_handler.encrypt_data(str(data_str))
    data_hash = dm_data_handler.generate_hash(data_str)

    metadata = {
      "key": key,
      "hash": data_hash,
      "file_path": f"{start_timestamp}_{end_timestamp}/{address}",
      "file_name": f"{block_before}_{block_after}.parquet",
    }

    os.makedirs(f"./tmp/{metadata['file_path']}", exist_ok=True)
    dm_data_handler.write_compressed_parquet(data_encrypted, f"./tmp/{metadata['file_path']}/{metadata['file_name']}")

  
  
  # mostrar saida do comando hdfs dfs -ls /
  subp = subprocess.Popen(["hdfs", "dfs", "-ls", "hdfs://namenode:9000/"], stdout=subprocess.PIPE)
  print(subp.communicate())

  subp = subprocess.Popen(["hdfs", "dfs", "-put", "./tmp", "hdfs://namenode:9000/raw/batch"], stdout=subprocess.PIPE)
  print(subp.communicate())


if __name__ == "__main__":
  
  NETWORK = "mainnet"
  ADDRESS = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
  API_KEY_NAME = "etherscan-api-key-2"
  AKV_NODE_NAME = 'DMEtherscanAsAService'

  main(NETWORK, ADDRESS, AKV_NODE_NAME, API_KEY_NAME)

  
