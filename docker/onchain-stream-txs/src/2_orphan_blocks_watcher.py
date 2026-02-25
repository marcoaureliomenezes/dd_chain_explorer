import argparse
import logging
import os

from configparser import ConfigParser
from logging import Logger
from typing import Dict, Any, Callable

from utils.dm_redis import DMRedis
from utils.dm_web3_client import Web3Handler
from utils.dm_schema_reg_client import get_schema
from utils.dm_kafka_client import KafkaHandler
from utils.dm_logger import KafkaLoggingHandler

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
    self.block_cache: DMRedis = sink_properties['block_cache']
    self.producer_mined_blocks_events = sink_properties['producer_mined_blocks_events']
    return self
  

  def recognize_orphaned_blocks(self, safe_block_number: int, safe_block_hash: str):
    prev_block_hash = self.block_cache.get(str(safe_block_number))
    if prev_block_hash and prev_block_hash != safe_block_hash:
      return True
    return False

  def handle_orphaned_blocks_cache(self, mined_block: Dict, delay_counter: int) -> None:
    block_number = mined_block["value"]["block_number"]
    block_hash   = mined_block["value"]["block_hash"]

    # Persiste o bloco atual no Redis
    self.block_cache.set(str(block_number), block_hash)

    # Remove entradas mais antigas que a janela de confirmação
    safe_block_key = block_number - delay_counter
    keys_to_delete = [k for k in self.block_cache.keys() if int(k) < safe_block_key]
    if keys_to_delete:
      self.block_cache.delete(*keys_to_delete)


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
      delay_counter = delay_counter + 1 if delay_counter < self.num_confirmations else self.num_confirmations
      counter += 1


if __name__ == "__main__":
    
  APP_NAME = "ORPHAN_BLOCKS_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  SSM_SECRET_NAME = os.getenv("AKV_SECRET_NAME")
  KAFKA_BROKERS = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  TOPIC_MINED_BLOCKS_EVENTS = os.getenv("TOPIC_MINED_BLOCKS_EVENTS")
  CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID")
  REDIS_DB_BLOCK_CACHE = int(os.getenv("REDIS_DB_BLOCK_CACHE", 2))
  NUM_CONFIRMATIONS = 10

  parser = argparse.ArgumentParser(description=f'Orphan blocks watcher — rede {NETWORK}')
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config consumers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  logging.basicConfig(level=logging.INFO, format='%(name)s — %(levelname)s — %(message)s')
  LOGGER = logging.getLogger(APP_NAME)

  PRODUCER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['producer.general.config']}
  CONSUMER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['consumer.general.config'], "group.id": CONSUMER_GROUP_ID}

  handler_kafka = KafkaHandler(LOGGER, sc_url=SCHEMA_REGISTRY_URL)

  # Kafka logging handler — writes log records to mainnet.0.application.logs
  schema_app_logs = get_schema(
      schema_name="application-logs-schema",
      schema_path="schemas/0_application_logs_avro.json",
  )
  producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
  LOGGER.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
  LOGGER.info("Kafka logging handler configured.")

  # Schema for mined blocks events (producer + consumer share the same schema)
  MINED_BLOCKS_EVENTS_PATH = 'schemas/1_mined_block_event_schema_avro.json'
  schema_mined_blocks_events = get_schema(
      schema_name="mined-block-event-schema",
      schema_path=MINED_BLOCKS_EVENTS_PATH,
  )

  consumer_mined_blocks_events = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_mined_blocks_events)
  LOGGER.info("AVRO CONSUMER for mined blocks events configured.")

  producer_mined_blocks_events = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_mined_blocks_events)
  LOGGER.info("AVRO PRODUCER for mined blocks events configured.")

  handler_web3 = Web3Handler(LOGGER, NETWORK).get_node_connection(SSM_SECRET_NAME, 'alchemy')
  LOGGER.info("Blockchain Node Connection configured.")

  # Cache persistênte de hashes de blocos — sobrevive a restarts do container
  block_cache = DMRedis(db=REDIS_DB_BLOCK_CACHE, logger=LOGGER)
  LOGGER.info(f"Redis block cache configured (db={REDIS_DB_BLOCK_CACHE}).")

  src_properties = {
    "handler_web3": handler_web3,
    "num_confirmations": NUM_CONFIRMATIONS,
    "consumer_mined_blocks_events": consumer_mined_blocks_events,
    "topic_mined_blocks_Events": TOPIC_MINED_BLOCKS_EVENTS,
  }

  sink_properties = {
    "block_cache": block_cache,
    "producer_mined_blocks_events": producer_mined_blocks_events,
  }

  BLOCK_MINER = (
    OrphanBlocksProcessor(LOGGER)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(callback=handler_kafka.message_handler)
  )