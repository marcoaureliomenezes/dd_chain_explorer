import argparse
import logging
import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from configparser import ConfigParser
from logging import Logger
from redis import Redis
from typing import Dict, Any, Callable

from utils.logger_utils import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.kafka_utils import KafkaHandler
from utils.schema_reg_utils import SchemaRegistryHandler
from utils.web3_utils import Web3Handler
from chain_extractor import ChainExtractor


class OrphanBlocksProcessor(ChainExtractor):

  def __init__(self, logger: Logger):
    self.logger = logger

  def src_config(self, src_properties: Dict[str, Any]):
    self.handler_web3 = src_properties["handler_web3"]
    self.num_confirmations = src_properties["num_confirmations"]
    self.consumer_mined_blocks_events = src_properties["consumer_mined_blocks_events"]
    self.topic_mined_blocks_Events = src_properties["topic_mined_blocks_Events"]
    self.consumer_mined_blocks_events.subscribe([self.topic_mined_blocks_Events])
    return self

  def sink_config(self, sink_properties: Dict[str, Any]):
    self.redis_client = sink_properties["redis_client"]
    self.producer_mined_blocks_events = sink_properties['producer_mined_blocks_events']
    return self
  

  def recognize_orphaned_blocks(self, safe_block_number: int, safe_block_hash: str):
    prev_block_hash = self.redis_client.get(str(safe_block_number))
    if prev_block_hash and prev_block_hash != safe_block_hash: return True
    return False

  def handle_orphaned_blocks_cache(self, mined_block: Dict, delay_counter: int) -> None:
    """
    This method is responsible for handling the cache of orphaned blocks.
    It stores the mined block data in a Redis cache and deletes the older than 'delay_counter' blocks.
    @param mined_block: Dict - Mined block data
    @param delay_counter: int - Number of confirmations to consider a block safe"""
    block_number = mined_block["value"]["block_number"]
    block_hash = mined_block["value"]["block_hash"]
    self.redis_client.set(block_number, block_hash)
    safe_block_key = block_number - delay_counter
    keys_to_delete = [key for key in self.redis_client.keys() if int(key) < safe_block_key]
    _ = [self.redis_client.delete(key) for key in keys_to_delete]


  def run(self, callback: Callable):
    counter = 0
    delay_counter = 0
    for mined_block in self.consuming_topic(self.consumer_mined_blocks_events):
      self.handle_orphaned_blocks_cache(mined_block, delay_counter)
      prev_block_number = mined_block["value"]["block_number"] - delay_counter
      safe_block_data = self.handler_web3.extract_block_data(prev_block_number)
      safe_block_data = self.handler_web3.parse_block_data(safe_block_data)
      safe_block_number, safe_block_hash = safe_block_data["number"], safe_block_data["hash"]
      is_orphan = self.recognize_orphaned_blocks(safe_block_number, safe_block_hash)
      if is_orphan:
        print(f"Orphan block {safe_block_number} detected")
        block_timestamp = safe_block_data['timestamp']
        block_number = safe_block_data['number']
        block_hash = safe_block_data['hash']
        print(type(block_timestamp), type(block_number), type(block_hash))
        key = "orphan"
        value = {"block_timestamp": block_timestamp, "block_number": block_number, "block_hash": block_hash}
        self.producer_mined_blocks_events.produce(self.topic_mined_blocks_Events, key=key, value=value, on_delivery=callback)
        self.producer_mined_blocks_events.flush()
    
       
      else:
        if counter % 10 == 0:
          self.logger.info(f"Safe block {safe_block_number} confirmed")
          safe_block_data
        # self.producer_mined_blocks.flush()
        # self.logger.info(f"Orphan block {orphan_block['number']} produced to topic {self.topics['topic_orphan_blocks']}")
        # self.logger.info(f"Safe block {safe_block['number']} produced to topic {self.topics['topic_mined_blocks']}")
      delay_counter = delay_counter + 1 if delay_counter < self.num_confirmations else self.num_confirmations
      counter += 1


if __name__ == "__main__":
    
  APP_NAME = "ORPHAN_BLOCKS_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  AKV_SECRET_NAME = os.getenv("AKV_SECRET_NAME")
  AKV_NODE_NAME = os.getenv("AKV_NODE_NAME")
  KAFKA_BROKERS = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")} 
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  REDIS_DB = 4
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  TOPIC_MINED_BLOCKS_EVENTS = os.getenv("TOPIC_MINED_BLOCKS_EVENTS")
  CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID")
  NUM_CONFIRMATIONS = 10

  parser = argparse.ArgumentParser(description=f'Streaming de blocos minerados na rede {NETWORK}')
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config Consumers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  # Configurando Logging
  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  ConsoleLoggingHandler = ConsoleLoggingHandler()
  LOGGER.addHandler(ConsoleLoggingHandler)

  LOGGER.info("Creating Kafka Producers for app logs, mined blocks data and transactions hash ids")
  PRODUCER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['producer.general.config']}
  CONSUMER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['consumer.general.config'], "group.id": CONSUMER_GROUP_ID}
  handler_kafka = KafkaHandler(LOGGER, SCHEMA_REGISTRY_URL)
  handler_schema_registry = SchemaRegistryHandler(SCHEMA_REGISTRY_URL)

  # Creating AVRO PRODUCER for app logs
  LOG_SCHEMA_PATH = 'schemas/0_application_logs_avro.json'
  schema_logs = handler_schema_registry.get_fixed_avro_schema(LOG_SCHEMA_PATH)
  producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_logs)
  kafka_handler = KafkaLoggingHandler(producer_logs, TOPIC_LOGS)
  LOGGER.addHandler(kafka_handler)
  LOGGER.info("AVRO Producer for app logs configured and added to logger")

  # Creating AVRO CONSUMER for mined blocks data
  MINED_BLOCKS_EVENTS_PATH = 'schemas/1_mined_block_event_schema_avro.json'
  schema_mined_blocks_events = handler_schema_registry.get_fixed_avro_schema(MINED_BLOCKS_EVENTS_PATH)
  consumer_mined_blocks_events = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_mined_blocks_events)
  LOGGER.info("AVRO CONSUMER for mined blocks events topic configured.")
  producer_mined_blocks_events = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_mined_blocks_events)
  LOGGER.info("AVRO PRODUCER for mined blocks events configured.")


  redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, db=REDIS_DB, decode_responses=True)

  # Configuring Blockchain Node Connection. Needs a secret in Azure Key Vault for an API Key
  AKV_URL = f'https://{AKV_NODE_NAME}.vault.azure.net/'
  AKV_CLIENT = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())
  handler_web3 = Web3Handler(LOGGER,  AKV_CLIENT, NETWORK).get_node_connection(AKV_SECRET_NAME, 'alchemy')
  LOGGER.info("Blockchain Node Connection configured.")

  src_properties = {
    "handler_web3": handler_web3,
    "num_confirmations": NUM_CONFIRMATIONS,
    "consumer_mined_blocks_events": consumer_mined_blocks_events,
    "topic_mined_blocks_Events": TOPIC_MINED_BLOCKS_EVENTS
  }

  sink_properties = {
    "redis_client": redis_client,
    "producer_mined_blocks_events": producer_mined_blocks_events,
  }
  
  BLOCK_MINER = (
    OrphanBlocksProcessor(LOGGER)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(callback=handler_kafka.message_handler)
  )
