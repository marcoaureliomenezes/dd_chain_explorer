import argparse
import logging
import os
import time

from logging import Logger
from typing import Dict, Generator, Optional, Callable, List, Any
from configparser import ConfigParser

from utils.web3_utils import Web3Handler
from utils.schema_registry_utils import get_schema
from utils.kafka_admin_client import KafkaAdminClient
from utils.kafka_utils import KafkaHandler
from utils.logger_utils import KafkaLoggingHandler


class MinedBlocksWatcher:

  def __init__(self, logger: Logger):
    self.logger = logger


  def src_config(self, src_properties: Dict[str, Any]):
    self.handler_web3 = src_properties["handler_web3"]
    return self


  def sink_config(self, sink_properties: Dict[str, Any]):
    self.producer_event_mined_blocks = sink_properties['producer_event_mined_blocks']
    self.topic_event_mined_blocks = sink_properties['topic_event_mined_blocks']
    return self
  

  def extract_stream(self, frequency: int) -> Generator:
    prev_block_number = 0
    while True:
      actual_block = self.handler_web3.extract_block_data()
      if actual_block:
        actual_block_number = actual_block.get('number')
        if actual_block_number == prev_block_number + 1:
          yield actual_block
      prev_block_number = actual_block_number
      time.sleep(float(frequency))
      

  def run(self, frequency: int, callback: Callable = None) -> None:
    for block_data in self.extract_stream(frequency):
      key = str(block_data['number'])
      block_timestamp = block_data['timestamp']
      block_number = block_data['number']
      block_hash = bytes.hex(block_data['hash'])

      value = {"block_timestamp": block_timestamp, "block_number": block_number, "block_hash": block_hash}
      self.producer_event_mined_blocks.produce(self.topic_event_mined_blocks, key="mined", value=value, on_delivery=callback)
      self.producer_event_mined_blocks.flush()
      LOGGER.info(f"Block Mined;{value}")
      print(f"Block Mined;{value}")
  




if __name__ == '__main__':
    
  APP_NAME = "MINED_BLOCKS_EVENTS"
  NETWORK = os.getenv("NETWORK")
  KAFKA_BROKERS = {'bootstrap.servers': os.getenv("KAFKA_BROKERS")} 
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  TOPIC_MINED_BLOCKS_EVENTS = os.getenv("TOPIC_MINED_BLOCKS_EVENTS")
  SSM_SECRET_NAME = os.getenv('AKV_SECRET_NAME')
  CLOCK_FREQUENCY = float(os.getenv("CLOCK_FREQUENCY"))
  

  parser = argparse.ArgumentParser(description=f'Streaming de blocos minerados na rede {NETWORK}')
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Configurações de producers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)

  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  LOGGER = logging.getLogger(APP_NAME)

  LOGGER.info("Creating Kafka producers and schemas")
  PRODUCER_CONF = {"client.id": APP_NAME.lower(), **KAFKA_BROKERS, **config['producer.general.config']}


  # Creating AVRO Producers for mined blocks data
  MINED_BLOCKS_EVENT_SCHEMA_PATH = 'schemas/1_mined_block_event_schema_avro.json'
  schema_mined_blocks_events = get_schema(
      schema_name="mined-block-event-schema",
      schema_path=MINED_BLOCKS_EVENT_SCHEMA_PATH,
  )
  print(schema_mined_blocks_events)


  # Test connection with MSK
  conf = {
    **KAFKA_BROKERS,
    'client.id': 'python-admin'
}
  kafka_admin = KafkaAdminClient(LOGGER, conf)

  kafka_admin.list_topics()

  handler_kafka = KafkaHandler(LOGGER, sc_url=SCHEMA_REGISTRY_URL)

  # Kafka logging handler — writes log records to mainnet.0.application.logs
  schema_app_logs = get_schema(
      schema_name="application-logs-schema",
      schema_path="schemas/0_application_logs_avro.json",
  )
  producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
  LOGGER.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
  LOGGER.info("Kafka logging handler configured.")

  producer_mined_blocks_events = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_mined_blocks_events)

  
  LOGGER.info("AVRO Producer for mined blocks data configured.")

  # Configuring Blockchain Node Connection. Needs a secret in Azure Key Vault for an API Key
  # AKV_URL = f'https://{AKV_NODE_NAME}.vault.azure.net/'
  # AKV_CLIENT = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())
  
  handler_web3 = Web3Handler(LOGGER, NETWORK).get_node_connection(SSM_SECRET_NAME, 'alchemy')
  LOGGER.info("Blockchain Node Connection configured.")

  src_properties = {"handler_web3": handler_web3}
  sink_properties = {
    "producer_event_mined_blocks": producer_mined_blocks_events,
    "topic_event_mined_blocks": TOPIC_MINED_BLOCKS_EVENTS
  }

  LOGGER.info("Starting Mined Blocks Processor")
  _ = (
     MinedBlocksWatcher(LOGGER)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(CLOCK_FREQUENCY, callback=handler_kafka.message_handler)
  )
