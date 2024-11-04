import argparse
import uuid
import logging
import os
from redis import Redis

from web3.exceptions import TransactionNotFound
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from configparser import ConfigParser
from utils.blockchain_node_connector import BlockchainNodeConnector

from utils.log_handlers import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.kafka_handlers import SchemaRegistryHandler
from utils.api_keys_manager import APIKeysManager
from utils.dm_utils import DataMasterUtils

class RawTransactionsProcessor:

  def __init__(self, logger, topics, schema_registry_handler, txs_threshold=100):
    self.logger = logger
    self.topic_input = topics["input"]
    self.topic_output = topics["output"]
    self.schema_registry_handler = schema_registry_handler
    self.txs_threshold = txs_threshold

    self.actual_api_key = None
    self.web3 = None                   
    self.consumer_txs_hash_ids = None
    self.producer_txs_data = None


  def set_web3_node_connection(self, api_key_name):
    self.web3 = self.node_conn.get_node_connection(api_key_name, 'infura')
    self.actual_api_key = api_key_name
    
  def consuming_topic(self, consumer):
    while True:
      msg = consumer.poll(timeout=0.1)
      if msg: yield msg.key()

  def config_node_conn(self, node_conn):
    self.node_conn = node_conn
    return self
  
  def config_consumer_txs_hash_ids(self, consumer):
    self.consumer_txs_hash_ids = consumer
    return self
  
  def config_producer_txs_data(self, producer):
    self.producer_txs_data = producer
    return self

  def config_api_keys_manager(self, api_keys_manager):
    self.api_keys_manager = api_keys_manager
    return self


  def parse_to_transaction_schema(self, tx_data):
    tx_data_parsed = DataMasterUtils.convert_hexbytes_to_str(dict(tx_data))
    return {
      "blockHash": tx_data_parsed["blockHash"],
      "blockNumber": tx_data_parsed["blockNumber"],
      "hash": tx_data_parsed["hash"],
      "transactionIndex": tx_data_parsed["transactionIndex"],
      "from": tx_data_parsed["from"],
      "to": tx_data_parsed["to"] if tx_data_parsed["to"] else "",
      "value": str(tx_data_parsed["value"]),
      "input": tx_data_parsed["input"],
      "gas": tx_data_parsed["gas"],
      "gasPrice": tx_data_parsed["gasPrice"],
      "maxFeePerGas": tx_data_parsed.get("maxFeePerGas"),
      "maxPriorityFeePerGas": tx_data_parsed.get("maxPriorityFeePerGas"),
      "nonce": tx_data_parsed["nonce"],
      "v": tx_data_parsed["v"],
      "r": tx_data_parsed["r"],
      "s": tx_data_parsed["s"],
      "type": tx_data_parsed["type"],
      "accessList": tx_data_parsed.get("accessList", [])
    }


  def capture_tx_data(self, tx_id):
    try:
      tx_data = self.web3.eth.get_transaction(tx_id)
      self.logger.info(f"API_request;{self.actual_api_key}")
      return tx_data
    except TransactionNotFound:
      self.logger.error(f"Transaction not found: {tx_id}")


  def produce_txs_data(self, tx_data):
    msg_key = str(tx_data['hash']) 
    self.producer_txs_data.produce(
      self.topic_output,
      key=msg_key,
      value=tx_data,
      on_delivery=self.schema_registry_handler.message_handler
    )
    self.producer_txs_data.poll(1)

  def run(self):
    self.api_keys_manager.free_api_keys()
    actual_api_key = self.api_keys_manager.elect_new_api_key()
    self.set_web3_node_connection(actual_api_key)
    self.api_keys_manager.check_api_key_request(actual_api_key)
    counter = 1
    self.consumer_txs_hash_ids.subscribe([self.topic_input])

    for msg in self.consuming_topic(self.consumer_txs_hash_ids):
      raw_transaction_data = self.capture_tx_data(msg)
      self.api_keys_manager.check_api_key_request(actual_api_key)
      if not raw_transaction_data: continue
      
      cleaned_transaction_data = self.parse_to_transaction_schema(raw_transaction_data)
      try: self.produce_txs_data(cleaned_transaction_data)
      except Exception as e: 
        self.logger.error(f"Error producing message: {e}")
        print(raw_transaction_data)
        
      if not api_keys_manager.check_if_api_key_is_mine(actual_api_key):
        self.logger.info(f"API KEY {actual_api_key} is being used by another process.")
        new_api_key = self.api_keys_manager.elect_new_api_key()
        if new_api_key:
          actual_api_key = new_api_key
          self.set_web3_node_connection(actual_api_key)

      if counter % self.txs_threshold  == 0:
        self.logger.info(f"API KEY {actual_api_key} reached throughput threshold.")
        new_api_key = self.api_keys_manager.elect_new_api_key()
        if new_api_key: 
          api_keys_manager.release_api_key_from_semaphore(actual_api_key)
          actual_api_key = new_api_key
          self.set_web3_node_connection(actual_api_key)
          self.api_keys_manager.check_api_key_request(actual_api_key)

      if counter % 10 == 0: self.api_keys_manager.free_api_keys()
      
      counter += 1
  




if __name__ == '__main__':

  APP_NAME="RAW_TXS_CRAWLER"
  network = os.getenv("NETWORK")
  kafka_brokers = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL")
  topic_logs = os.getenv("TOPIC_LOGS")
  consumer_group = os.getenv("CONSUMER_GROUP")

  redis_host = os.getenv("REDIS_HOST")
  redis_port = os.getenv("REDIS_PORT")
  redis_password = os.getenv("REDIS_PASS")
  akv_vault_name = os.getenv("AKV_NODE_NAME")
  api_key_names_compacted = os.getenv('AKV_SECRET_NAMES')
  TX_THROUGHPUT_THRESHOLD = 100
  redis_db_apk_semaphore, redis_db_apk_counter = 0, 1

  PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

  app_topics = {
    "input": os.getenv("TOPIC_TXS_HASH_IDS"),
    "output": os.getenv("TOPIC_TXS_RAW_DATA")
  }


  parser = argparse.ArgumentParser(description=APP_NAME)
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config Producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config Consumers')
  args = parser.parse_args()

  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  logger = logging.getLogger(f"{APP_NAME}_{PROC_ID}")
  logger.setLevel(logging.INFO)
  logger.addHandler(ConsoleLoggingHandler())



  # Configure Redis Client for API Keys management
  redis_common_parms = dict(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)
  redis_client_apk_semaphore = Redis(**redis_common_parms, db=redis_db_apk_semaphore)
  redis_client_apk_counter = Redis(**redis_common_parms, db=redis_db_apk_counter)

  api_keys_manager = APIKeysManager(
    logger,
    PROC_ID,
    redis_client_apk_semaphore,
    redis_client_apk_counter,
    api_key_names_compacted
  )


  # Configure Kafka and Schema Registry Handler for Avro Schemas management
  schema_registry_handler = SchemaRegistryHandler(logger, schema_registry_url)
  common_conf = {**kafka_brokers,  "client.id": PROC_ID}
  producer_conf = {**common_conf, **config['producer.general.config']}
  consumer_conf = {**common_conf, **config['consumer.general.config'], "group.id": consumer_group}

  # Configure Kafka Producer for logs
  logs_schema = schema_registry_handler.get_avro_schema("schemas/application_logs_avro.json")
  producer_logs = schema_registry_handler.create_avro_producer(producer_conf, logs_schema)
  kafka_handler = KafkaLoggingHandler(producer_logs, topic_logs)
  logger.addHandler(kafka_handler)

  # Configure Kafka Consumer for txs_hash_ids
  txs_hash_ids_schema = schema_registry_handler.get_avro_schema("schemas/txs_hash_ids.json")
  consumer_txs_hash_ids = schema_registry_handler.create_avro_consumer(consumer_conf, txs_hash_ids_schema)

  # Configure Kafka Producer for txs_data
  txs_data_schema = schema_registry_handler.get_avro_schema("schemas/transactions_schema_avro.json")
  producer_txs_data = schema_registry_handler.create_avro_producer(producer_conf, txs_data_schema)

  # Configure Node Connector for Web3 API using Azure Key Vault Secrets
  akv_url = f'https://{akv_vault_name}.vault.azure.net/'
  akv_client = SecretClient(vault_url=akv_url, credential=DefaultAzureCredential())
  node_connector = BlockchainNodeConnector(logger, akv_client, network)
  

  raw_txs_processor = RawTransactionsProcessor(
    logger, app_topics, schema_registry_handler, TX_THROUGHPUT_THRESHOLD)
  
  _ = (
    raw_txs_processor
      .config_node_conn(node_connector)
      .config_consumer_txs_hash_ids(consumer_txs_hash_ids)
      .config_producer_txs_data(producer_txs_data)
      .config_api_keys_manager(api_keys_manager)
      .run()
  )

