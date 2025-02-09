import boto3
import logging
import os

import json

from datetime import datetime as dt, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from utils.etherscan_utils import EthercanAPI
from utils.logging_utils import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.schema_registry_utils import SchemaRegistryUtils
from utils.kafka_utils import KafkaUtils


class ContractTransactionsCrawler:

  def __init__(self, logger, contract_address):
    self.logger = logger
    self.contract_address_default = contract_address
    self.timestamp_interval = None
    self.block_interval = None
    self.paths = None
    self.__configure_pagination()


  def __configure_pagination(self, page=1, offset=100, sort='asc'):
    self.page = page
    self.offset = offset
    self.sort = sort
    return self


  def read_config(self, dynamodb_client, etherscan_client):
    self.etherscan_client = etherscan_client
    self.dynamodb_client = dynamodb_client
    return self
  

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
    blocks_interval = f"blocks_from_{self.block_interval[0]}_to_{self.block_interval[1]}"
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

  def run(self):
    all_contract_data = []
    self.__config_file_name(self.contract_address_default)
    for data in self.__get_transactions(self.contract_address_default):
      all_contract_data.extend(data)
    if self.check_file_exists(self.paths['s3']):
      self.logger.info(f"File {self.paths['s3']} already exists in S3. Skipping...")
      return
    os.remove(self.paths['local']) if os.path.exists(self.paths['local']) else None
    with open(self.paths['local'], 'w') as f:
      f.write(json.dumps(all_contract_data))
    self.s3_client.upload_file(self.paths['local'], Bucket=self.bucket, Key=self.paths['s3'])



    # def config_file_prefix(self, s3_path, server, execution_date):
    #   partitioned_path = dt.strftime(execution_date, 'year=%Y/month=%m/day=%d')
    #   self.paths = {"local": f"/tmp/{server}/{partitioned_path}", "s3": f"{s3_path}/{server}/{partitioned_path}"}
    #   _ = os.makedirs(self.paths["local"], exist_ok=True)
    #   self.logger.info(f"local_path:{self.paths['local']};lake_path:{self.paths['s3']}")
    #   return self
      # if not self.overwrite: 
      #   hdfs_file_exists = self.check_hdfs_file_exists(block_before)
      #   if hdfs_file_exists:
      #     self.logger.info(f"file_exists:{hdfs_file_exists}")
      #     block_before = hdfs_file_exists.split("_")[-1].split(".")[0]
      #     if block_before != block_after:
      #       continue   



  # def __run_config_checks(self):
  #   assert self.etherscan_client is not None, "Etherscan client not configured"
  #   assert self.s3 is not None, "S3 client not configured"
  #   assert self.timestamp_interval is not None, "Timestamp interval not configured"
  #   assert self.contract_address is not None, "Contract address not configured"
  #   assert self.basepath is not None, "Basepath not configured"


  # def __write_compressed_parquet(self, json_data, path):
  #   df_data = pd.DataFrame(json_data)
  #   table = pa.Table.from_pandas(df_data)
  #   pq.write_table(table, path, compression='SNAPPY')


    

if __name__ == "__main__":
  
  APP_NAME = "CONTRACT_TRANSACTIONS_CRAWLER"
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  KAFKA_BROKERS = os.getenv("KAFKA_BROKERS")
  SR_URL = os.getenv("SR_URL")
  CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
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
  s3_client = boto3.client('s3',
      endpoint_url=os.getenv("S3_URL"),
      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
  )

  # CONFIGURING AWS CLIENT FOR DYNAMODB. Purpose: Get popular smart contracts to crawl
  dynamodb_client = boto3.client('dynamodb',
      endpoint_url=os.getenv("DYNAMODB_URL"),
      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
  )

  # CONFIGURING ETHERSCAN CLIENT. Purpose: Get transactions from smart contracts.
  etherscan_client = EthercanAPI(LOGGER, akv_client, os.getenv("APK_NAME"), os.getenv("NETWORK"))

  crawler = (
    ContractTransactionsCrawler(LOGGER, CONTRACT_ADDRESS)
      .read_config(dynamodb_client, etherscan_client)
      .write_config(s3_client, bucket=S3_BUCKET, bucket_prefix=S3_BUCKET_PREFIX, overwrite=False)
      .interval_config(os.getenv("EXEC_DATE"))
      .run()
  )


  # example of date format '%Y-%m-%d %H:%M:%S%z'
  date = "2021-09-01 00:00:00+00:00"
