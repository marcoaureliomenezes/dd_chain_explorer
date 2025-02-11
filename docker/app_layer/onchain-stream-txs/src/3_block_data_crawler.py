import argparse
import logging
import os
import time

from logging import Logger
from typing import Dict, Generator, Optional, Callable, List, Any
from configparser import ConfigParser
from requests import HTTPError

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from utils.logger_utils import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.kafka_utils import KafkaHandler
from utils.schema_reg_utils import SchemaRegistryHandler
from utils.web3_utils import Web3Handler
from chain_extractor import ChainExtractor


class BlockDataCrawler(ChainExtractor):


  def __init__(self, logger: Logger):
    self.logger = logger


  def src_config(self, src_properties: Dict[str, Any]):
    self.handler_web3 = src_properties["handler_web3"]
    self.consumer_mined_blocks_events = src_properties["consumer_mined_blocks_events"]
    self.topic_mined_blocks_events = src_properties["topic_mined_blocks_events"]
    self.consumer_mined_blocks_events.subscribe([self.topic_mined_blocks_events])
    self.logger.info("AVRO CONSUMER for mined blocks events topic configured.")
    return self


  def sink_config(self, sink_properties: Dict[str, Any]):
    self.producer_mined_blocks = sink_properties['producer_mined_blocks']
    self.topic_mined_blocks = sink_properties['topic_mined_blocks']
    self.producer_txs_hash_ids = sink_properties['producer_txs_hash_ids']
    self.topic_txs_hash_ids = sink_properties['topic_txs_hash_ids']
    self.txs_threshold = sink_properties['txs_threshold']
    self.num_partitions_hash_ids = int(sink_properties['num_partitions_hash_ids'])
    return self
      

  def batch_txs_hash_ids(self, txs_list: List[str]):
    txs_list = txs_list[:self.txs_threshold] if self.txs_threshold else txs_list
    txs_partition_list = [(txs_list[i], i % self.num_partitions_hash_ids) for i in range(self.num_partitions_hash_ids)]
    for hash_id, partition in txs_partition_list:
      key, value = hash_id, {"tx_hash": hash_id}
      self.producer_txs_hash_ids.produce(topic=TOPIC_TXS_HASH_IDS, key=key, value=value, partition=partition)
    self.producer_txs_hash_ids.flush()
    


  def run(self, callback: Callable) -> None:
    for block_event in self.consuming_topic(self.consumer_mined_blocks_events):
      block_data = self.handler_web3.extract_block_data(block_event["value"]["block_number"])
      cleaned_data = self.handler_web3.parse_block_data(block_data)
      key, value = str(cleaned_data['number']), cleaned_data
      self.producer_mined_blocks.produce(self.topic_mined_blocks, key=key, value=value, on_delivery=callback)
      self.producer_mined_blocks.flush()
      self.batch_txs_hash_ids(txs_list=cleaned_data["transactions"])
      LOGGER.info(f"Kafka_Ingestion;TOPIC:{TOPIC_TXS_HASH_IDS};NUM TRANSACTIONS:{len(value["transactions"])};BLOCK NUMBER:{key}, source: {block_event["key"]}")
  

if __name__ == '__main__':
    
  APP_NAME = "BLOCK_DATA_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  AKV_NODE_NAME = os.getenv('AKV_NODE_NAME')
  AKV_SECRET_NAME = os.getenv('AKV_SECRET_NAME')
  KAFKA_BROKERS = {'bootstrap.servers': os.getenv("KAFKA_BROKERS")} 
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_MINED_BLOCKS_EVENTS = os.getenv("TOPIC_MINED_BLOCKS_EVENTS")
  CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  TOPIC_MINED_BLOCKS = os.getenv("TOPIC_MINED_BLOCKS")
  TOPIC_TXS_HASH_IDS = os.getenv("TOPIC_TXS_HASH_IDS")

  TOPIC_TXS_HASH_IDS_PARTITIONS = int(os.getenv("TOPIC_TXS_HASH_IDS_PARTITIONS"))
  CLOCK_FREQUENCY = float(os.getenv("CLOCK_FREQUENCY"))
  TXS_PER_BLOCK = int(os.getenv("TXS_PER_BLOCK"))
  
  parser = argparse.ArgumentParser(description=f'Streaming de blocos minerados na rede {NETWORK}')
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config Consumers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  ConsoleLoggingHandler = ConsoleLoggingHandler()
  LOGGER.addHandler(ConsoleLoggingHandler)
  
  LOGGER.info("Creating Kafka Producers for app logs, mined blocks data and transactions hash ids")
  PRODUCER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['producer.general.config']}
  CONSUMER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['consumer.general.config'], "group.id": CONSUMER_GROUP_ID}
  handler_kafka = KafkaHandler(LOGGER, SCHEMA_REGISTRY_URL)
  handler_schema_registry = SchemaRegistryHandler(SCHEMA_REGISTRY_URL)


  TXS_HASH_IDS_SCHEMA_PATH = 'schemas/3_transaction_hash_ids_schema_avro.json'

  # Creating AVRO Producers for app logs
  LOG_SCHEMA_PATH = 'schemas/0_application_logs_avro.json'
  schema_logs = handler_schema_registry.get_fixed_avro_schema(LOG_SCHEMA_PATH)
  producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_logs)
  kafka_handler = KafkaLoggingHandler(producer_logs, TOPIC_LOGS)
  LOGGER.addHandler(kafka_handler)
  LOGGER.info("AVRO Producer for app logs configured and added to logger")

  # Creating AVRO CONSUMER for mined blocks events
  MINED_BLOCKS_EVENTS_PATH = 'schemas/1_mined_block_event_schema_avro.json'
  schema_mined_blocks_events = handler_schema_registry.get_fixed_avro_schema(MINED_BLOCKS_EVENTS_PATH)
  consumer_mined_blocks_events = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_mined_blocks_events)
  LOGGER.info("AVRO CONSUMER for mined blocks events topic configured.")

  # Creating AVRO Producers for mined blocks data
  BLOCK_SCHEMA_PATH = 'schemas/2_block_data_schema_avro.json'
  schema_block_data = handler_schema_registry.get_fixed_avro_schema(BLOCK_SCHEMA_PATH)
  producer_block_data = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_block_data)
  LOGGER.info("AVRO Producer for mined blocks data configured.")

  # Creating AVRO Producers for transactions hash ids
  schema_txs_hash_ids = handler_schema_registry.get_fixed_avro_schema(TXS_HASH_IDS_SCHEMA_PATH)
  producer_txs_hash_ids = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_txs_hash_ids)
  LOGGER.info("AVRO Producer for transactions hash ids configured.")

  # Configuring Blockchain Node Connection. Needs a secret in Azure Key Vault for an API Key
  AKV_URL = f'https://{AKV_NODE_NAME}.vault.azure.net/'
  AKV_CLIENT = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())
  handler_web3 = Web3Handler(LOGGER,  AKV_CLIENT, NETWORK).get_node_connection(AKV_SECRET_NAME, 'alchemy')
  LOGGER.info("Blockchain Node Connection configured.")

  src_properties = {
    "handler_web3": handler_web3,
    "consumer_mined_blocks_events": consumer_mined_blocks_events,
    "topic_mined_blocks_events": TOPIC_MINED_BLOCKS_EVENTS
    }
  sink_properties = {
    "producer_mined_blocks": producer_block_data,
    "topic_mined_blocks": TOPIC_MINED_BLOCKS,
    "producer_txs_hash_ids": producer_txs_hash_ids,
    "topic_txs_hash_ids": TOPIC_TXS_HASH_IDS,
    "txs_threshold": TXS_PER_BLOCK,
    "num_partitions_hash_ids": TOPIC_TXS_HASH_IDS_PARTITIONS
  }

  LOGGER.info("Starting Mined Blocks Processor")
  _ = (
     BlockDataCrawler(LOGGER)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(callback=handler_kafka.message_handler)
  )
