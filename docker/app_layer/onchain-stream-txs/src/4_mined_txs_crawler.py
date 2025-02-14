import argparse
import uuid
import logging
import os
from redis import Redis
from typing import Dict, Any
from logging import Logger

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from configparser import ConfigParser


from dm_33_utils.web3_utils import Web3Handler
from dm_33_utils.schema_reg_utils import SchemaRegistryHandler
from dm_33_utils.logger_utils import ConsoleLoggingHandler, KafkaLoggingHandler
from dm_33_utils.kafka_utils import KafkaHandler


from utils.api_keys_manager import APIKeysManager
from chain_extractor import ChainExtractor


class RawTransactionsProcessor(ChainExtractor):

  def __init__(self, logger: Logger):
    self.logger = logger

  def src_config(self, src_properties: Dict[str, Any]):
    self.consumer_txs_hash_ids = src_properties['consumer_txs_hash_ids']
    topic_txs_hash_ids = src_properties['topic_txs_hash_ids']
    self.consumer_txs_hash_ids.subscribe([topic_txs_hash_ids])
    self.logger.info(f"Crawling transactions from topic: {topic_txs_hash_ids}")
    self.web3 = src_properties["web3_handler"]
    self.actual_api_key = src_properties["actual_api_key"]
    #self.node_conn.get_node_connection(api_key_name, 'infura')
    return self


  def sink_config(self, sink_properties: Dict[str, Any]):
    self.api_keys_manager = sink_properties['api_keys_manager']
    self.producer_txs_data = sink_properties['producer_txs_data']
    self.topic_txs_data = sink_properties['topic_txs_data']
    return self
  

  def run(self, callback: Any) -> None:
    self.api_keys_manager.free_api_keys()
    actual_api_key = self.api_keys_manager.elect_new_api_key()
    self.web3.get_node_connection(actual_api_key, 'infura')
    self.api_keys_manager.check_api_key_request(actual_api_key)
    counter = 1
    self.txs_threshold = 100
    for msg in self.consuming_topic(self.consumer_txs_hash_ids):
      raw_transaction_data = self.web3.extract_tx_data(msg['value']['tx_hash'])
      self.api_keys_manager.check_api_key_request(actual_api_key)
      if not raw_transaction_data: continue
      cleaned_transaction_data = self.web3.parse_transaction_data(raw_transaction_data)
      try:
        key, value = cleaned_transaction_data['hash'], cleaned_transaction_data
        self.producer_txs_data.produce(self.topic_txs_data, key=key, value=value, on_delivery=callback)
        self.producer_txs_data.flush()
      except Exception as e: 
        self.logger.error(f"Error producing message: {e}")
        print(raw_transaction_data)
    
        
      if not api_keys_manager.check_if_api_key_is_mine(actual_api_key):
        self.logger.info(f"API KEY {actual_api_key} is being used by another process.")
        new_api_key = self.api_keys_manager.elect_new_api_key()
        if new_api_key:
          actual_api_key = new_api_key
          self.web3.get_node_connection(actual_api_key, 'infura')

      if counter % self.txs_threshold  == 0:
        self.logger.info(f"API KEY {actual_api_key} reached throughput threshold.")
        new_api_key = self.api_keys_manager.elect_new_api_key()
        if new_api_key: 
          api_keys_manager.release_api_key_from_semaphore(actual_api_key)
          actual_api_key = new_api_key
          self.web3.get_node_connection(actual_api_key, 'infura')
          self.api_keys_manager.check_api_key_request(actual_api_key)

      if counter % 10 == 0: self.api_keys_manager.free_api_keys()
      counter += 1
  


if __name__ == '__main__':

  APP_NAME="RAW_TXS_CRAWLER"
  network = os.getenv("NETWORK")
  kafka_brokers = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL")
  topic_logs = os.getenv("TOPIC_LOGS")
  topic_txs_hash_ids = os.getenv("TOPIC_TXS_HASH_IDS")
  consumer_group = os.getenv("CONSUMER_GROUP")
  topic_txs_data = os.getenv("TOPIC_TXS_DATA")
  redis_host = os.getenv("REDIS_HOST")
  redis_port = os.getenv("REDIS_PORT")
  redis_password = os.getenv("REDIS_PASS")
  akv_vault_name = os.getenv("AKV_NODE_NAME")
  api_key_names_compacted = os.getenv('AKV_SECRET_NAMES')
  TX_THROUGHPUT_THRESHOLD = 100
  redis_db_apk_semaphore = 0
  redis_db_apk_counter = 1

  PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

  parser = argparse.ArgumentParser(description=APP_NAME)
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config Producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config Consumers')
  args = parser.parse_args()

  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  logger = logging.getLogger(APP_NAME)
  logger.setLevel(logging.INFO)
  logger.addHandler(ConsoleLoggingHandler())

  # Configure Kafka and Schema Registry Handler for Avro Schemas management
  common_conf = {**kafka_brokers,  "client.id": PROC_ID}
  producer_conf = {**common_conf, **config['producer.general.config']}
  consumer_conf = {**common_conf, **config['consumer.general.config'], "group.id": consumer_group}
  handler_kafka = KafkaHandler(logger, schema_registry_url)
  handler_schema_registry = SchemaRegistryHandler(schema_registry_url)

  
  # Configure Kafka Producer for logs
  schema_topic_logs = handler_schema_registry.get_fixed_avro_schema("schemas/0_application_logs_avro.json")
  producer_logs = handler_kafka.create_avro_producer(producer_conf, schema_topic_logs)
  kafka_handler = KafkaLoggingHandler(producer_logs, topic_logs)
  logger.addHandler(kafka_handler)
  logger.info("AVRO Producer for app logs configured and added to logger")

  # Configure Kafka Consumer for txs_hash_ids
  txs_hash_ids_schema = handler_schema_registry.get_fixed_avro_schema("schemas/3_transaction_hash_ids_schema_avro.json")
  consumer_txs_hash_ids = handler_kafka.create_avro_consumer(consumer_conf, txs_hash_ids_schema)
  logger.info("AVRO CONSUMER for transactions hash ids topic configured.")

  # Configure Kafka Producer for txs_data
  txs_data_schema = handler_schema_registry.get_fixed_avro_schema("schemas/4_transactions_schema_avro.json")
  producer_txs_data = handler_kafka.create_avro_producer(producer_conf, txs_data_schema)
  logger.info("AVRO PRODUCER for transactions data configured.")


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



  # Configure Node Connector for Web3 API using Azure Key Vault Secrets
  akv_url = f'https://{akv_vault_name}.vault.azure.net/'
  akv_client = SecretClient(vault_url=akv_url, credential=DefaultAzureCredential())
  node_connector = Web3Handler(logger, akv_client, network)
  
  src_properties = {
    "web3_handler": node_connector,
    "actual_api_key": None,
    "consumer_txs_hash_ids": consumer_txs_hash_ids,
    "topic_txs_hash_ids": topic_txs_hash_ids

  }

  sink_properties = {
    "api_keys_manager": api_keys_manager,
    "producer_txs_data": producer_txs_data,
    "topic_txs_data": topic_txs_data,
    "txs_threshold": TX_THROUGHPUT_THRESHOLD
  }


  _ = (
    RawTransactionsProcessor(logger)
      .src_config(src_properties)
      .sink_config(sink_properties)
      # .config_node_conn(node_connector)
      # .config_consumer_txs_hash_ids(consumer_txs_hash_ids)
      # .config_producer_txs_data(producer_txs_data)
      # .config_api_keys_manager(api_keys_manager)
      .run(callback=handler_kafka.message_handler)
  )

