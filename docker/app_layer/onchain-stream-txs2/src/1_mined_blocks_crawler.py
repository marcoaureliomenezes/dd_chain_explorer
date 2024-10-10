import argparse
import json
import logging
import os
import time

from configparser import ConfigParser
from requests import HTTPError
from confluent_kafka import Producer

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from utils.log_handlers import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.kafka_handlers import SchemaRegistryHandler
from utils.blockchain_node_connector import BlockchainNodeConnector


class MinedBlocksProcessor:

  def __init__(self, logger):
    self.logger = logger
    self.node_conn = None
    self.web3 = None
    self.schema_registry_handler = None
    self.producer_mined_blocks = None
    self.producer_txs_hash_ids = None
    self.producer_logs = None
    self.topics = None


  def get_avro_schema(self, avro_path):
    with open(avro_path) as f:
      return json.dumps(json.load(f))
    

  def config_node_conn(self, network, akv_client, apk_name):
    self.api_key_name = apk_name
    self.node_conn = BlockchainNodeConnector(self.logger, akv_client, network)
    self.web3 = self.node_conn.get_node_connection(apk_name, 'alchemy')
    self.logger.info("Blockchain node connection configured")
    return self


  def config_schema_registry_handler(self, sr_url):
    self.schema_registry_handler = SchemaRegistryHandler(self.logger, sr_url)
    self.logger.info("Schema Registry configured")
    return self
  

  def config_producer_mined_blocks(self, producer_configs, avro_schema_path):
    avro_schema = self.get_avro_schema(avro_schema_path)
    self.producer_mined_blocks = self.schema_registry_handler.create_avro_producer(producer_configs, avro_schema)
    self.logger.info("Producer for mined blocks data configured")
    return self
  
  
  def config_producer_txs_hash_ids(self, producer_configs, avro_schema_path):
    avro_schema = self.get_avro_schema(avro_schema_path)
    self.producer_txs_hash_ids = self.schema_registry_handler.create_avro_producer(producer_configs, avro_schema)
    self.logger.info("Producer for transactions hash ids configured")
    return self


  def config_producer_logs(self, producer_configs, avro_schema_path, topic):
    avro_schema = self.get_avro_schema(avro_schema_path)
    self.producer_logs = self.schema_registry_handler.create_avro_producer(producer_configs, avro_schema)
    self.logger.info("Producer for app logs configured")
    kafka_handler = KafkaLoggingHandler(self.producer_logs, topic)
    self.logger.addHandler(kafka_handler)
    return self
  
  
  def config_topic_names(self, topic_mined_blocks, topic_txs_hash_ids):
    self.topics = {"topic_mined_blocks": topic_mined_blocks, "topic_txs_hash_ids": topic_txs_hash_ids}
    self.logger.info(f"Topic MINED BLOCK: {topic_mined_blocks}")
    self.logger.info(f"Topic TRANSACTIONS HASH IDs: {topic_txs_hash_ids}")
    return self
  
  def config_txs_threshold(self, txs_threshold):
    self.txs_threshold = int(txs_threshold)
    self.logger.info(f"Transactions threshold of {txs_threshold} configured")
    return self

  def __get_latest_block(self):
    try: block_info = self.web3.eth.get_block('latest')
    except HTTPError as e:
      self.logger.error(f"API_request;{self.api_key_name};Error:{str(e)}")
    else:      
      self.logger.info(f"API_request;{self.api_key_name}")
      return block_info


  def __parse_to_block_clock_schema(self, block_raw_data):
    return {
      "number": block_raw_data['number'],
      "timestamp": block_raw_data['timestamp'],
      "hash": bytes.hex(block_raw_data['hash']),
      "parentHash": bytes.hex(block_raw_data['parentHash']),
      "difficulty": block_raw_data['difficulty'],
      "totalDifficulty": str(block_raw_data['totalDifficulty']),
      "nonce": bytes.hex(block_raw_data['nonce']),
      "size": block_raw_data['size'],
      "miner": block_raw_data['miner'],
      "baseFeePerGas": block_raw_data['baseFeePerGas'],
      "gasLimit": block_raw_data['gasLimit'],
      "gasUsed": block_raw_data['gasUsed'],
      "logsBloom": bytes.hex(block_raw_data['logsBloom']),
      "extraData": bytes.hex(block_raw_data['extraData']),
      "transactionsRoot": bytes.hex(block_raw_data['transactionsRoot']),
      "stateRoot": bytes.hex(block_raw_data['stateRoot']),
      "transactions": [bytes.hex(i) for i in block_raw_data['transactions']],
      "withdrawals": [dict(i) for i in block_raw_data['withdrawals']]
    }
  

  def limit_transactions(self, block_data):
    if not self.txs_threshold: return block_data
    else: return block_data[:self.txs_threshold]
  

  def __streaming_block_data(self, frequency):
    previous_block = 0
    self.counter = 0
    while 1:
      actual_block = self.__get_latest_block()
      if not actual_block: continue
      if actual_block != previous_block:
        yield actual_block
        previous_block = actual_block
      time.sleep(float(frequency))


  def batch_txs_hash_ids(self, txs_list, block_number):
    txs_list = self.limit_transactions(txs_list)
    for tx_hash_id_index in range(len(txs_list)):
      partition = tx_hash_id_index % int(TOPIC_TXS_HASH_IDS_PARTITIONS)
      message_key = txs_list[tx_hash_id_index]
      value = {"tx_hash": message_key}
      self.producer_txs_hash_ids.produce(topic=TOPIC_TXS_HASH_IDS, key=message_key, value=value, partition=partition)
    self.producer_txs_hash_ids.flush()
    LOGGER.info(f"Kafka_Ingestion;TOPIC:{TOPIC_TXS_HASH_IDS};NUM TRANSACTIONS:{len(txs_list)};BLOCK NUMBER:{block_number}")


  def __run_config_checks(self):
    assert self.node_conn is not None, "Node Connection not configured"
    assert self.web3 is not None, "Web3 client not configured"
    assert self.schema_registry_handler is not None, "Schema Registry Handler not configured"
    assert self.producer_mined_blocks is not None, "Mined Blocks Producer not configured"
    assert self.producer_txs_hash_ids is not None, "Transactions Hash Ids Producer not configured"
    assert self.producer_logs is not None, "Logs Producer not configured"
    assert self.topics is not None, "Kafka topics not configured"


  def run(self, frequency):
    self.__run_config_checks()
    for raw_block_data in self.__streaming_block_data(frequency):
      cleaned_block_data = self.__parse_to_block_clock_schema(raw_block_data)
      key = str(cleaned_block_data['number'])
      self.producer_mined_blocks.produce(
        TOPIC_MINED_BLOCKS,
        key=key,
        value=cleaned_block_data,
        on_delivery=self.schema_registry_handler.message_handler
      )
      self.producer_mined_blocks.flush()
      self.batch_txs_hash_ids(txs_list=cleaned_block_data["transactions"], block_number=key)

  

if __name__ == '__main__':
    
  APP_NAME = "MINED_BLOCKS_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  KAFKA_BROKERS = {'bootstrap.servers': os.getenv("KAFKA_BROKERS")} 
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  TOPIC_MINED_BLOCKS = os.getenv("TOPIC_MINED_BLOCKS")
  TOPIC_TXS_HASH_IDS = os.getenv("TOPIC_TXS_HASH_IDS")
  AKV_NODE_NAME = os.getenv('AKV_NODE_NAME')
  AKV_SECRET_NAME = os.getenv('AKV_SECRET_NAME')

  TOPIC_TXS_HASH_IDS_PARTITIONS = int(os.getenv("TOPIC_TXS_HASH_IDS_PARTITIONS"))
  CLOCK_FREQUENCY = float(os.getenv("CLOCK_FREQUENCY"))
  TXS_PER_BLOCK = int(os.getenv("TXS_PER_BLOCK"))
  
  BLOCK_SCHEMA_PATH = 'schemas/block_metadata_avro.json'
  LOG_SCHEMA_PATH = 'schemas/application_logs_avro.json'
  TXS_HASH_IDS_SCHEMA_PATH = 'schemas/txs_hash_ids.json'

  parser = argparse.ArgumentParser(description=f'Streaming de blocos minerados na rede {NETWORK}')
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Configurações de producers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)

  AKV_URL = f'https://{AKV_NODE_NAME}.vault.azure.net/'
  AKV_CLIENT = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())

  LOGGER = logging.getLogger(APP_NAME)
  LOGGER.setLevel(logging.INFO)
  ConsoleLoggingHandler = ConsoleLoggingHandler()
  LOGGER.addHandler(ConsoleLoggingHandler)
  
  PRODUCER_CONF = {**KAFKA_BROKERS, **config['producer.general.config'], **{"client.id": APP_NAME.lower()}}
  BLOCK_MINER = (
    MinedBlocksProcessor(LOGGER)
      .config_node_conn(NETWORK, AKV_CLIENT, AKV_SECRET_NAME)
      .config_schema_registry_handler(SCHEMA_REGISTRY_URL)
      .config_producer_logs(PRODUCER_CONF, LOG_SCHEMA_PATH, TOPIC_LOGS)
      .config_producer_mined_blocks(PRODUCER_CONF, BLOCK_SCHEMA_PATH)
      .config_producer_txs_hash_ids(PRODUCER_CONF, TXS_HASH_IDS_SCHEMA_PATH)
      .config_topic_names(TOPIC_MINED_BLOCKS, TOPIC_TXS_HASH_IDS)
      .config_txs_threshold(TXS_PER_BLOCK)
      .run(CLOCK_FREQUENCY)
  )
