import argparse
import json
import logging
import os

from configparser import ConfigParser
from requests import HTTPError

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from redis import Redis

from utils.log_handlers import ConsoleLoggingHandler, KafkaLoggingHandler
from utils.blockchain_node_connector import BlockchainNodeConnector
from utils.kafka_handlers import SchemaRegistryHandler


class OrphanBlocksProcessor:

  def __init__(self, logger):
    self.logger = logger
    self.node_conn = None
    self.web3 = None
    self.redis_client = None
    self.producer_mined_blocks = None
    self.schema_registry_handler = None
    self.consumer_mined_blocks = None


  def get_avro_schema(self, avro_path):
    with open(avro_path) as f:
      return json.dumps(json.load(f))
    

  def consuming_topic(self, consumer):
    while True:
      msg = consumer.poll(timeout=0.1)
      if msg: yield {"key": msg.key(), "value": msg.value()}


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
  

  def config_redis_client(self, host, port, password, db):
    self.redis_client = Redis(host=host, port=port, password=password, decode_responses=True, db=db)
    self.logger.info("Redis Client configured")
    return self

  def config_num_confirmations(self, num_confirmations):
    self.num_confirmations = num_confirmations
    self.logger.info("Number of confirmations configured")
    return self

  def config_producer_mined_blocks(self, producer_configs, avro_schema_path):
    avro_schema = self.get_avro_schema(avro_schema_path)
    self.producer_mined_blocks = self.schema_registry_handler.create_avro_producer(producer_configs, avro_schema)
    self.logger.info("Producer for mined blocks data configured")
    return self
  

  def config_consumer_mined_blocks(self, consumer_configs, avro_schema_path):
    avro_schema = self.get_avro_schema(avro_schema_path)
    self.consumer_mined_blocks = self.schema_registry_handler.create_avro_consumer(consumer_configs, avro_schema)
    self.logger.info("Consumer for mined blocks data configured")
    return self
  

  def config_producer_orphan_blocks(self, producer_configs, avro_schema_path):
    avro_schema = self.get_avro_schema(avro_schema_path)
    self.producer_orphan_blocks = self.schema_registry_handler.create_avro_producer(producer_configs, avro_schema)
    self.logger.info("Producer for orphan blocks data configured")
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
  

  def config_topic_names(self, topic_mined_blocks, topic_orphan_blocks, topic_txs_hash_ids):
    self.topics = {
      "topic_mined_blocks": topic_mined_blocks,
      "topic_orphan_blocks": topic_orphan_blocks,
      "topic_txs_hash_ids": topic_txs_hash_ids
    }
    self.logger.info(f"Topic MINED BLOCK: {topic_mined_blocks}")
    self.logger.info(f"Topic TRANSACTIONS HASH IDs: {topic_txs_hash_ids}")
    return self
  

  def get_block_data(self, identifier='latest'):
    try: block_data = self.web3.eth.get_block(identifier)
    except HTTPError as e:
      self.logger.error(f"API_request;{self.api_key_name};Error:{str(e)}")
    else:
      self.logger.info(f"API_request;{self.api_key_name}")
      return block_data


  def parse_to_block_clock_schema(self, block_raw_data):
    return {
      "number": block_raw_data['number'],
      "timestamp": block_raw_data['timestamp'],
      "hash": bytes.hex(block_raw_data['hash']),
      "parentHash": bytes.hex(block_raw_data['parentHash']),
      "difficulty": block_raw_data['difficulty'],
      "totalDifficulty": str(block_raw_data.get('totalDifficulty')),
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


  def recognize_orphaned_blocks(self, mined_block_data, delay_counter):
    mined_block_number = mined_block_data["value"]["number"]
    safe_block_number = mined_block_number - delay_counter
    safe_block_data = self.get_block_data(safe_block_number)
    safe_block_data = self.parse_to_block_clock_schema(safe_block_data)
    cached_block_data = self.redis_client.get(str(safe_block_number))
    if cached_block_data:
      cached_block_data = json.loads(cached_block_data)
      cached_block_data = cached_block_data["value"]
      if safe_block_data["hash"] == cached_block_data["hash"] and safe_block_data["miner"] == cached_block_data["miner"]:
        self.logger.info(f"Block {mined_block_number} is safe with {delay_counter} confirmations")
      else:
        self.logger.info(f"Block {mined_block_number} IS ORPHAN")
        return cached_block_data, safe_block_data


  def handle_orphaned_blocks_cache(self, mined_block_data, delay_counter):
    mined_block_number = mined_block_data["value"]["number"]
    self.redis_client.set(mined_block_number, json.dumps(mined_block_data))
    safe_block_key = mined_block_number - delay_counter
    redis_block_number_keys = self.redis_client.keys()
    keys_to_delete = [key for key in redis_block_number_keys if int(key) < safe_block_key]
    for key in keys_to_delete:
      self.redis_client.delete(key)


  def __run_config_checks(self):
    assert self.node_conn is not None, "Node Connection not configured"
    assert self.web3 is not None, "Web3 client not configured"
    assert self.schema_registry_handler is not None, "Schema Registry Handler not configured"
    assert self.producer_mined_blocks is not None, "Mined Blocks Producer not configured"
    assert self.consumer_mined_blocks is not None, "Mined Blocks Consumer not configured"
    assert self.producer_txs_hash_ids is not None, "Transactions Hash Ids Producer not configured"
    assert self.producer_orphan_blocks is not None, "Orphan Blocks Producer not configured"
    assert self.producer_logs is not None, "Logs Producer not configured"
    assert self.redis_client is not None, "Redis Client not configured"
    assert self.topics is not None, "Kafka topics not configured"


  def run(self):
    delay_counter = 0
    self.__run_config_checks()
    self.consumer_mined_blocks.subscribe([self.topics["topic_mined_blocks"]])
    for mined_block_data in self.consuming_topic(self.consumer_mined_blocks):
      self.handle_orphaned_blocks_cache(mined_block_data, delay_counter)
      safe_block_result = self.recognize_orphaned_blocks(mined_block_data, delay_counter)
      if safe_block_result:
        orphan_block, safe_block = safe_block_result
        self.producer_mined_blocks.produce(topic=self.topics["topic_orphan_blocks"], value=orphan_block)
        self.producer_mined_blocks.produce(topic=self.topics["topic_mined_blocks"], value=safe_block)
        self.producer_mined_blocks.flush()
        self.logger.info(f"Orphan block {orphan_block['number']} produced to topic {self.topics['topic_orphan_blocks']}")
        self.logger.info(f"Safe block {safe_block['number']} produced to topic {self.topics['topic_mined_blocks']}")
      delay_counter = delay_counter + 1 if delay_counter < self.num_confirmations else self.num_confirmations



if __name__ == "__main__":
    
  APP_NAME = "ORPHAN_BLOCKS_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  KAFKA_BROKERS = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")} 
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS = os.getenv("TOPIC_LOGS")
  TOPIC_MINED_BLOCKS = os.getenv("TOPIC_MINED_BLOCKS")
  TOPIC_ORPHAN_BLOCKS = os.getenv("TOPIC_ORPHAN_BLOCKS")
  TOPIC_TXS_HASH_IDS = os.getenv("TOPIC_TXS_HASH_IDS")
  TOPIC_TXS_HASH_IDS_PARTITIONS = int(os.getenv("TOPIC_TXS_HASH_IDS_PARTITIONS"))
  CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID")

  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  AKV_SECRET_NAME = os.getenv("AKV_SECRET_NAME")
  AKV_NODE_NAME = os.getenv("AKV_NODE_NAME")

  REDIS_DB = 4
  NUM_CONFIRMATIONS = 10
  PATH_SCHEMA_BLOCKS = "schemas/block_metadata_avro.json"
  PATH_SCHEMA_LOGS = "schemas/application_logs_avro.json"
  PATH_SCHEMA_TXS_HASH = "schemas/application_logs_avro.json"
  AKV_URL = f'https://{AKV_NODE_NAME}.vault.azure.net/'
  AKV_CLIENT = SecretClient(vault_url=AKV_URL, credential=DefaultAzureCredential())

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

  COMMON_CONF = {**KAFKA_BROKERS,  "client.id": APP_NAME.lower()}
  PRODUCER_CONF = {**COMMON_CONF, **config['producer.general.config']}
  CONSUMER_CONF = {**COMMON_CONF, **config['consumer.general.config'], "group.id": CONSUMER_GROUP_ID}
  BLOCK_MINER = (
    OrphanBlocksProcessor(LOGGER)
      .config_node_conn(NETWORK, AKV_CLIENT, AKV_SECRET_NAME)
      .config_schema_registry_handler(SCHEMA_REGISTRY_URL)
      .config_producer_logs(PRODUCER_CONF, PATH_SCHEMA_LOGS, TOPIC_LOGS)
      .config_producer_mined_blocks(PRODUCER_CONF, PATH_SCHEMA_BLOCKS)
      .config_producer_orphan_blocks(PRODUCER_CONF, PATH_SCHEMA_BLOCKS)
      .config_consumer_mined_blocks(CONSUMER_CONF, PATH_SCHEMA_BLOCKS)
      .config_producer_txs_hash_ids(PRODUCER_CONF, PATH_SCHEMA_TXS_HASH)
      .config_topic_names(TOPIC_MINED_BLOCKS, TOPIC_ORPHAN_BLOCKS, TOPIC_TXS_HASH_IDS)
      .config_redis_client(REDIS_HOST, REDIS_PORT, REDIS_PASS, REDIS_DB)
      .config_num_confirmations(NUM_CONFIRMATIONS)
      .run()
  )

