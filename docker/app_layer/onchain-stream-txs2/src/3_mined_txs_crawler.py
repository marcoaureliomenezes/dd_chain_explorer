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

class RawTransactionsProcessor:

  def __init__(self, logger, schema_registry_handler, txs_threshold=100):
    self.txs_threshold = txs_threshold
    self.logger = logger
    self.schema_registry_handler = schema_registry_handler
    self.actual_api_key = None
    self.web3 = None                   
    self.consumer_txs_hash_ids = None
    self.producer_txs_data = None
    self.topics = None


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

  def config_topic_names(self, topics):
    self.topics = topics
    return self

  def parse_to_transaction_schema(self, tx_data):
    access_list = tx_data.get("accessList")
    if access_list:
      access_list = [dict(access_item) for access_item in tx_data.get("accessList")]
      access_list = [{"address": item["address"], "storageKeys": [bytes.hex(i) for i in item["storageKeys"]]} for item in access_list]
    else:
      access_list = []
    return {
      "blockHash": bytes.hex(tx_data["blockHash"]),
      "blockNumber": tx_data["blockNumber"],
      "hash": bytes.hex(tx_data["hash"]),
      "transactionIndex": tx_data["transactionIndex"],
      "from": tx_data["from"],
      "to": tx_data["to"] if tx_data["to"] else "",
      "value": str(tx_data["value"]),
      "input": bytes.hex(tx_data["input"]),
      "gas": tx_data["gas"],
      "gasPrice": tx_data["gasPrice"],
      "maxFeePerGas": tx_data.get("maxFeePerGas"),
      "maxPriorityFeePerGas": tx_data.get("maxPriorityFeePerGas"),
      "nonce": tx_data["nonce"],
      "v": tx_data["v"],
      "r": bytes.hex(tx_data["r"]),
      "s": bytes.hex(tx_data["s"]),
      "type": tx_data["type"],
      "accessList": access_list
    }


  def capture_tx_data(self, tx_id):
    try:
      tx_data = self.web3.eth.get_transaction(tx_id)
      self.logger.info(f"API_request;{self.actual_api_key}")
      return tx_data
    except TransactionNotFound:
      self.logger.error(f"Transaction not found: {tx_id}")


  def check_type_transaction(self, tx_data):
    if tx_data['to'] == None: 
      return self.topics["output"]["topic_tx_contract_deploy"]
    elif tx_data['input'] == '': 
      return self.topics["output"]["topic_txs_token_transfer"]
    else: return self.topics["output"]["topic_tx_contract_call"]


  def produce_txs_data(self, tx_data):
    msg_key = str(tx_data['hash']) 
    topic = self.check_type_transaction(tx_data)
    self.producer_txs_data.produce(topic, key=msg_key, value=tx_data, on_delivery=self.schema_registry_handler.message_handler)
    self.producer_txs_data.poll(1)

  def run(self):
    self.api_keys_manager.free_api_keys()
    actual_api_key = self.api_keys_manager.elect_new_api_key()
    self.set_web3_node_connection(actual_api_key)
    self.api_keys_manager.check_api_key_request(actual_api_key)
    counter = 1
    self.consumer_txs_hash_ids.subscribe([self.topics["input"]["topic_txs_hash_ids"]])

    for msg in self.consuming_topic(self.consumer_txs_hash_ids):
      raw_transaction_data = self.capture_tx_data(msg)
      self.api_keys_manager.check_api_key_request(actual_api_key)
      if not raw_transaction_data: continue
      cleaned_transaction_data = self.parse_to_transaction_schema(raw_transaction_data)
      
      try: self.produce_txs_data(cleaned_transaction_data)
      except Exception as e: 
        self.logger.error(f"Error producing message: {e}")
        print(cleaned_transaction_data)
        
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
  KAFKA_BROKERS = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL")
  topic_logs = os.getenv("TOPIC_LOGS")
  consumer_group = os.getenv("CONSUMER_GROUP")

  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  AKV_NODE_NAME = os.getenv("AKV_NODE_NAME")
  api_key_names_compacted = os.getenv('AKV_SECRET_NAMES')

  app_topics = dict(
    input = {"topic_txs_hash_ids": os.getenv("TOPIC_TXS_HASH_IDS")},
    output = {
      "topic_tx_contract_deploy": os.getenv("TOPIC_TX_CONTRACT_DEPLOY"),
      "topic_txs_token_transfer": os.getenv("TOPIC_TX_TOKEN_TRANSFER"),
      "topic_tx_contract_call": os.getenv("TOPIC_TX_CONTRACT_CALL")
    }
  )


  redis_db_apk_semaphore, redis_db_apk_counter = 0, 1
  TX_THROUGHPUT_THRESHOLD = 100
  PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

  akv_url = f'https://{AKV_NODE_NAME}.vault.azure.net/'
  akv_client = SecretClient(vault_url=akv_url, credential=DefaultAzureCredential())

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

  common_conf = {**KAFKA_BROKERS,  "client.id": PROC_ID}
  producer_conf = {**common_conf, **config['producer.general.config']}
  consumer_conf = {**common_conf, **config['consumer.general.config'], "group.id": consumer_group}


  redis_common_parms = dict(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, decode_responses=True)
  redis_client_apk_semaphore = Redis(**redis_common_parms, db=redis_db_apk_semaphore)
  redis_client_apk_counter = Redis(**redis_common_parms, db=redis_db_apk_counter)

  api_keys_manager = APIKeysManager(
    logger,
    PROC_ID,
    redis_client_apk_semaphore,
    redis_client_apk_counter,
    api_key_names_compacted
  )

  node_connector = BlockchainNodeConnector(logger, akv_client, network)
  schema_registry_handler = SchemaRegistryHandler(logger, schema_registry_url)
  logs_schema = schema_registry_handler.get_avro_schema("schemas/application_logs_avro.json")
  txs_hash_ids_schema = schema_registry_handler.get_avro_schema("schemas/txs_hash_ids.json")
  txs_data_schema = schema_registry_handler.get_avro_schema("schemas/transactions_schema_avro.json")

  consumer_txs_hash_ids = schema_registry_handler.create_avro_consumer(consumer_conf, txs_hash_ids_schema)
  producer_txs_data = schema_registry_handler.create_avro_producer(producer_conf, txs_data_schema)
  producer_logs = schema_registry_handler.create_avro_producer(producer_conf, logs_schema)
  kafka_handler = KafkaLoggingHandler(producer_logs, topic_logs)
  logger.addHandler(kafka_handler)

  _ = (
    RawTransactionsProcessor(logger, schema_registry_handler, TX_THROUGHPUT_THRESHOLD)
      .config_node_conn(node_connector)
      .config_consumer_txs_hash_ids(consumer_txs_hash_ids)
      .config_producer_txs_data(producer_txs_data)
      .config_api_keys_manager(api_keys_manager)
      .config_topic_names(app_topics)
      .run()
  )

