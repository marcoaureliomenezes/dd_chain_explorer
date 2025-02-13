import boto3
import logging
import os
import redis
import json

from datetime import datetime as dt, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from utils.etherscan_utils import EthercanAPI
from utils.logger_utils import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.schema_reg_utils import SchemaRegistryUtils
from utils.kafka_utils import KafkaUtils


class ContractTransactionsCrawler:

  def __init__(self, logger):
    self.logger = logger
    self.timestamp_interval = None
    self.block_interval = None
    self.paths = None
    self.__configure_pagination()


  def __configure_pagination(self, page=1, offset=1000, sort='asc'):
    self.page = page
    self.offset = offset
    self.sort = sort
    return self


  def read_config(self, dynamodb_client, etherscan_client):
    self.etherscan_client = etherscan_client
    self.dynamodb_client = dynamodb_client
    return self
  
  def get_contracts(self):
    data = map(lambda key: (key, redis_client.get(key)), redis_client.keys())
    contracts_sorted = sorted(data, key=lambda x: int(x[1]), reverse=True)
    contracts_sorted = list(map(lambda x: x[0], contracts_sorted))
    return contracts_sorted

  def write_config(self, s3_client, bucket, bucket_prefix, overwrite=False):
    self.s3_client = s3_client
    self.bucket = bucket
    self.s3_bucket_prefix = bucket_prefix
    self.overwrite = overwrite
    return self

  def interval_config(self, end_date, window_hours=1):
    end_date = dt.strptime(end_date, '%Y-%m-%d %H:%M:%S%z')
    start_date = end_date - timedelta(hours=window_hours)
    start_timestamp, end_timestamp = int(start_date.timestamp()), int(end_date.timestamp())
    self.timestamp_interval = (start_timestamp, end_timestamp)
    self.logger.info(f"timestamp_start:{start_timestamp};timestamp_end:{end_timestamp}")
    self.block_interval = self.__get_block_interval()
    return self
  
  def __config_file_name(self, contract_addr):
    dat_hour = dt.fromtimestamp(self.timestamp_interval[0])
    blocks_interval = f"year={dat_hour.year}/month={dat_hour.month}/day={dat_hour.day}/hour={dat_hour.hour}"
    file_path = f"{blocks_interval}/{contract_addr}/transactions.json"
    self.paths = {"local": f"./tmp/{file_path}", "s3": f"{self.s3_bucket_prefix}/{file_path}"}
    local_path_dir = os.path.dirname(self.paths["local"])
    _ = os.makedirs(local_path_dir, exist_ok=True)
    self.logger.info(f"local_path:{self.paths['local']};lake_path:{self.paths['s3']}")
    return self
  
  

  def __get_block_interval(self):
    get_block = lambda timestamp, closest: self.etherscan_client.get_block_by_timestamp(timestamp, closest=closest)
    block_before = get_block(self.timestamp_interval[0], closest='after')
    block_after = get_block(self.timestamp_interval[1], closest='before')
    if block_before["message"] != "OK" or block_after["message"] != "OK": return
    block_interval = (block_before["result"], block_after["result"])
    self.logger.info(f"block_before:{block_before['result']};block_after:{block_after['result']}")
    return block_interval

  def get_contract_tx_data(self, contract_addr: str, block_before: int, block_after: int):
    args = (contract_addr, block_before, block_after, self.page, self.offset, self.sort)
    tx_data = self.etherscan_client.get_contract_tx_by_block_interval(*args)
    return tx_data

  def __get_transactions(self, contract_address):
    data = []
    lower_limit, upper_limit = self.__get_block_interval()
    block_before, block_after = lower_limit, upper_limit
    block_after = str(int(block_after) - 1)
    while block_before < block_after:
      result = self.get_contract_tx_data(contract_address, block_before, block_after)
      if result["message"] != "OK":return
      if data == result["result"]: return
      else: data = result["result"]
      block_before = data[-1]["blockNumber"]
      yield data
      
  def generate_file_name(self):
    pass

  def check_file_exists(self, path):
    try: self.s3.head_object(Bucket=self.bucket, Key=path) ; return True
    except: return False

  def write_to_s3(self, data):
    if self.check_file_exists(self.paths['s3']):
      self.logger.info(f"File {self.paths['s3']} already exists in S3. Skipping...")
      return
    os.remove(self.paths['local']) if os.path.exists(self.paths['local']) else None
    with open(self.paths['local'], 'w') as f:
      f.write(json.dumps(data))
    self.s3_client.upload_file(self.paths['local'], Bucket=self.bucket, Key=self.paths['s3'])


  def run(self):
    contracts = self.get_contracts()
    
    for contract in contracts:
      all_contract_data = []
      self.__config_file_name(contract)
      for data in self.__get_transactions(contract):
        all_contract_data.extend(data)
      print(f"Contract {contract} has {len(all_contract_data)} transactions")
      self.write_to_s3(all_contract_data)




    

if __name__ == "__main__":
  
  APP_NAME = "CONTRACT_TRANSACTIONS_CRAWLER"
  KAFKA_BROKERS = os.getenv("KAFKA_BROKERS")
  SR_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  REDIS_HOST = os.getenv("REDIS_HOST", "redis")
  REDIS_PORT = os.getenv("REDIS_PORT", "6379")
  REDIS_SECRET = os.getenv("REDIS_PASS", "secret")
  REDIS_DB = os.getenv("REDIS_DB", 3)

  AKV_URL = f"https://{os.getenv('AKV_NAME')}.vault.azure.net/"
  S3_BUCKET = os.getenv("S3_BUCKET")
  S3_BUCKET_PREFIX = os.getenv("S3_BUCKET_PREFIX")
  akv_client = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())
   
  # CONFIGURING LOGGING
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(ConsoleLoggingHandler())

  # CONFIGURING KAFKA PRODUCER FOR LOGGING
  sc_utils = SchemaRegistryUtils(SR_URL)
  kafka_utils = KafkaUtils(LOGGER, SR_URL)
  logs_schema = sc_utils.get_schema_by_subject("mainnet.0.application.logs-value")
  producer_conf = {"bootstrap.servers": KAFKA_BROKERS, "client.id": APP_NAME, "acks": 1}
  producer_logs = kafka_utils.create_avro_producer(producer_conf, logs_schema)
  kafka_handler = KafkaLoggingHandler(producer_logs, TOPIC_LOGS)
  LOGGER.addHandler(kafka_handler)

  # CONFIGURING AWS CLIENT FOR S3. Purpose: Save the raw data in S3
  s3_client = boto3.client('s3', endpoint_url=os.getenv("S3_URL")
  )

  redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_SECRET, decode_responses=True)
  # List all hashes in the Redis database
  #print(redis_client.keys())

  # CONFIGURING ETHERSCAN CLIENT. Purpose: Get transactions from smart contracts.
  etherscan_client = EthercanAPI(LOGGER, akv_client, os.getenv("APK_NAME"), os.getenv("NETWORK"))

  crawler = (
    ContractTransactionsCrawler(LOGGER)
      .read_config(redis_client, etherscan_client)
      .write_config(s3_client, bucket=S3_BUCKET, bucket_prefix=S3_BUCKET_PREFIX, overwrite=False)
      .interval_config(os.getenv("EXEC_DATE"))
      .run()
  )