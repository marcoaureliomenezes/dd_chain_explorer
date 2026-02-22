import argparse
import logging
import os

from logging import Logger
from typing import Dict, Callable, List, Any
from configparser import ConfigParser

from utils.web3_utils import Web3Handler
from utils.schema_registry_utils import get_schema
from utils.kafka_utils import KafkaHandler
from utils.logger_utils import KafkaLoggingHandler

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
    txs_partition_list = [(txs_list[i], i % self.num_partitions_hash_ids) for i in range(len(txs_list))]
    for hash_id, partition in txs_partition_list:
      key, value = hash_id, {"tx_hash": hash_id}
      self.producer_txs_hash_ids.produce(topic=self.topic_txs_hash_ids, key=key, value=value, partition=partition)
    self.producer_txs_hash_ids.flush()
    

  def run(self, callback: Callable) -> None:
    for block_event in self.consuming_topic(self.consumer_mined_blocks_events):
      block_data = self.handler_web3.extract_block_data(block_event["value"]["block_number"])
      cleaned_data = self.handler_web3.parse_block_data(block_data)
      key, value = str(cleaned_data['number']), cleaned_data
      self.producer_mined_blocks.produce(self.topic_mined_blocks, key=key, value=value, on_delivery=callback)
      self.producer_mined_blocks.flush()
      self.batch_txs_hash_ids(txs_list=cleaned_data["transactions"])
      self.logger.info(f"Kafka_Ingestion;TOPIC:{self.topic_txs_hash_ids};NUM TRANSACTIONS:{len(value['transactions'])};BLOCK NUMBER:{key}, source: {block_event['key']}")
  

if __name__ == '__main__':

  APP_NAME = "BLOCK_DATA_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  SSM_SECRET_NAME = os.getenv("AKV_SECRET_NAME")
  KAFKA_BROKERS = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS", "mainnet.0.application.logs")
  TOPIC_MINED_BLOCKS_EVENTS = os.getenv("TOPIC_MINED_BLOCKS_EVENTS")
  CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "cg_block_data_crawler")
  TOPIC_MINED_BLOCKS = os.getenv("TOPIC_MINED_BLOCKS")
  TOPIC_TXS_HASH_IDS = os.getenv("TOPIC_TXS_HASH_IDS")
  TOPIC_TXS_HASH_IDS_PARTITIONS = int(os.getenv("TOPIC_TXS_HASH_IDS_PARTITIONS", "8"))
  TXS_PER_BLOCK = int(os.getenv("TXS_PER_BLOCK", "50"))

  parser = argparse.ArgumentParser(description=f'Streaming de dados de blocos minerados na rede {NETWORK}')
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config consumers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  logger = logging.getLogger(APP_NAME)

  logger.info("Creating Kafka producers/consumer and schemas")
  PRODUCER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['producer.general.config']}
  CONSUMER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['consumer.general.config'], "group.id": CONSUMER_GROUP}
  handler_kafka = KafkaHandler(logger, sc_url=SCHEMA_REGISTRY_URL)

  # Kafka logging handler — writes log records to mainnet.0.application.logs
  schema_app_logs = get_schema(
    schema_name="application-logs-schema",
    schema_path="schemas/0_application_logs_avro.json",
  )
  producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
  logger.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
  logger.info("Kafka logging handler configured.")

  # Schemas
  schema_mined_blocks_events = get_schema(
    schema_name="mined-block-event-schema",
    schema_path="schemas/1_mined_block_event_schema_avro.json"
  )
  schema_block_data = get_schema(
    schema_name="block-data-schema",
    schema_path="schemas/2_block_data_schema_avro.json"
  )
  schema_txs_hash_ids = get_schema(
    schema_name="transaction-hash-ids-schema",
    schema_path="schemas/3_transaction_hash_ids_schema_avro.json"
  )

  # Kafka consumer and producers
  consumer_mined_blocks_events = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_mined_blocks_events)
  logger.info("AVRO consumer for mined blocks events topic configured.")

  producer_block_data = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_block_data)
  logger.info("AVRO producer for mined blocks data configured.")

  producer_txs_hash_ids = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_txs_hash_ids)
  logger.info("AVRO producer for transactions hash ids configured.")

  # Blockchain node connection via SSM
  handler_web3 = Web3Handler(logger, NETWORK).get_node_connection(SSM_SECRET_NAME, 'alchemy')
  logger.info("Blockchain node connection configured.")

  src_properties = {
    "handler_web3": handler_web3,
    "consumer_mined_blocks_events": consumer_mined_blocks_events,
    "topic_mined_blocks_events": TOPIC_MINED_BLOCKS_EVENTS,
  }

  sink_properties = {
    "producer_mined_blocks": producer_block_data,
    "topic_mined_blocks": TOPIC_MINED_BLOCKS,
    "producer_txs_hash_ids": producer_txs_hash_ids,
    "topic_txs_hash_ids": TOPIC_TXS_HASH_IDS,
    "txs_threshold": TXS_PER_BLOCK,
    "num_partitions_hash_ids": TOPIC_TXS_HASH_IDS_PARTITIONS,
  }

  logger.info("Starting Block Data Crawler")
  _ = (
    BlockDataCrawler(logger)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(callback=handler_kafka.message_handler)
  )
