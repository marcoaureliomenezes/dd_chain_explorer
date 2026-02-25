import argparse
import logging
import os
import uuid

from configparser import ConfigParser
from logging import Logger
from typing import Any, Dict

from requests import HTTPError
from utils.dm_redis import DMRedis
from utils.dm_web3_client import Web3Handler
from utils.dm_schema_reg_client import get_schema
from utils.dm_kafka_client import KafkaHandler
from utils.api_keys_manager import APIKeysManager
from utils.dm_logger import KafkaLoggingHandler

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

  def _rotate_api_key(self, old_api_key: str) -> str:
    """Libera a key atual, elege uma nova e reconecta o Web3. Retorna a nova key."""
    self.api_keys_manager.release_api_key_from_semaphore(old_api_key)
    new_api_key = self.api_keys_manager.elect_new_api_key()
    if not new_api_key:
      raise RuntimeError("Nenhuma API key Infura disponivel para rotacao.")
    self.web3.get_node_connection(new_api_key, 'infura')
    self.api_keys_manager.check_api_key_request(new_api_key)
    return new_api_key

  def _fetch_tx_with_rotation(self, tx_hash: str, actual_api_key: str):
    """Busca dados de transacao com retry automatico em caso de 429 (rate limit).

    Tenta cada key disponivel antes de desistir. Retorna (tx_data, actual_api_key).
    """
    max_retries = len(self.api_keys_manager.api_keys)
    for attempt in range(max_retries):
      try:
        tx_data = self.web3.extract_tx_data(tx_hash)
        return tx_data, actual_api_key
      except HTTPError as err:
        status = err.response.status_code if err.response is not None else None
        if status == 429:
          self.logger.warning(f"Rate limit (429) na key {actual_api_key}, tentativa {attempt + 1}/{max_retries}. Rotacionando.")
          actual_api_key = self._rotate_api_key(actual_api_key)
        else:
          self.logger.error(f"HTTPError inesperado buscando tx {tx_hash}: {err}")
          return None, actual_api_key
    self.logger.error(f"Todas as API keys rate-limited. Descartando tx {tx_hash}.")
    return None, actual_api_key
  

  def run(self, callback: Any) -> None:
    # Limpa TODO o semáforo na inicialização para remover entradas obsoletas
    # (ex: formato antigo de chave, réplicas mortas sem TTL expirado).
    self.api_keys_manager.free_api_keys(free_timeout=0)
    actual_api_key = self.api_keys_manager.elect_new_api_key()
    self.web3.get_node_connection(actual_api_key, 'infura')
    self.api_keys_manager.check_api_key_request(actual_api_key)
    counter = 1
    self.txs_threshold = 100
    for msg in self.consuming_topic(self.consumer_txs_hash_ids):
      raw_transaction_data, actual_api_key = self._fetch_tx_with_rotation(msg['value']['tx_hash'], actual_api_key)
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
    
        
      if not self.api_keys_manager.check_if_api_key_is_mine(actual_api_key):
        self.logger.info(f"API KEY {actual_api_key} is being used by another process.")
        new_api_key = self.api_keys_manager.elect_new_api_key()
        if new_api_key:
          actual_api_key = new_api_key
          self.web3.get_node_connection(actual_api_key, 'infura')

      if counter % self.txs_threshold == 0:
        self.logger.info(f"API KEY {actual_api_key} reached throughput threshold.")
        new_api_key = self.api_keys_manager.elect_new_api_key()
        if new_api_key:
          self.api_keys_manager.release_api_key_from_semaphore(actual_api_key)
          actual_api_key = new_api_key
          self.web3.get_node_connection(actual_api_key, 'infura')
          self.api_keys_manager.check_api_key_request(actual_api_key)

      if counter % 10 == 0: self.api_keys_manager.free_api_keys()
      counter += 1
  


if __name__ == '__main__':

  APP_NAME = "RAW_TXS_CRAWLER"
  NETWORK          = os.getenv("NETWORK")
  KAFKA_BROKERS    = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
  TOPIC_LOGS       = os.getenv("TOPIC_LOGS")
  TOPIC_TXS_HASH_IDS  = os.getenv("TOPIC_TXS_HASH_IDS")
  CONSUMER_GROUP   = os.getenv("CONSUMER_GROUP")
  TOPIC_TXS_DATA   = os.getenv("TOPIC_TXS_DATA")
  SSM_SECRET_NAME  = os.getenv("AKV_SECRET_NAME")          # nome do segredo SSM (api key Infura inicial)
  API_KEY_NAMES    = os.getenv("AKV_SECRET_NAMES")          # ex: 'infura-api-key-1-12'
  REDIS_DB_APK_SEMAPHORE = int(os.getenv("REDIS_DB_APK_SEMAPHORE", 0))
  REDIS_DB_APK_COUNTER   = int(os.getenv("REDIS_DB_APK_COUNTER",   1))
  TX_THROUGHPUT_THRESHOLD = 100

  PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

  parser = argparse.ArgumentParser(description=APP_NAME)
  parser.add_argument('config_producer', type=argparse.FileType('r'), help='Config Producers')
  parser.add_argument('config_consumer', type=argparse.FileType('r'), help='Config Consumers')
  args = parser.parse_args()
  config = ConfigParser()
  config.read_file(args.config_producer)
  config.read_file(args.config_consumer)

  logging.basicConfig(level=logging.INFO, format='%(name)s — %(levelname)s — %(message)s')
  logger = logging.getLogger(APP_NAME)

  PRODUCER_CONF = {"client.id": PROC_ID, **KAFKA_BROKERS, **config['producer.general.config']}
  CONSUMER_CONF = {"client.id": PROC_ID, **KAFKA_BROKERS, **config['consumer.general.config'], "group.id": CONSUMER_GROUP}

  handler_kafka = KafkaHandler(logger, sc_url=SCHEMA_REGISTRY_URL)

  # Schemas
  LOGS_SCHEMA_PATH         = 'schemas/0_application_logs_avro.json'
  TXS_HASH_IDS_SCHEMA_PATH = 'schemas/3_transaction_hash_ids_schema_avro.json'
  TXS_DATA_SCHEMA_PATH     = 'schemas/4_transactions_schema_avro.json'

  schema_app_logs     = get_schema(schema_name="application-logs-schema",       schema_path=LOGS_SCHEMA_PATH)
  schema_txs_hash_ids = get_schema(schema_name="transaction-hash-ids-schema",   schema_path=TXS_HASH_IDS_SCHEMA_PATH)
  schema_txs_data     = get_schema(schema_name="transactions-schema",            schema_path=TXS_DATA_SCHEMA_PATH)

  # Kafka logging handler — writes log records to TOPIC_LOGS
  producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
  logger.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
  logger.info("Kafka logging handler configured.")

  consumer_txs_hash_ids = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_txs_hash_ids)
  logger.info("AVRO CONSUMER for transactions hash ids configured.")

  producer_txs_data = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_txs_data)
  logger.info("AVRO PRODUCER for transactions data configured.")

  # Redis — semáforo de API keys e contador de requisições
  redis_semaphore = DMRedis(db=REDIS_DB_APK_SEMAPHORE, logger=logger)
  redis_counter   = DMRedis(db=REDIS_DB_APK_COUNTER,   logger=logger)
  api_keys_manager = APIKeysManager(logger, PROC_ID, redis_semaphore, redis_counter, API_KEY_NAMES)
  logger.info("API Keys Manager configured.")

  # Web3 — conecta ao nó Infura via SSM
  node_connector = Web3Handler(logger, NETWORK)
  logger.info("Web3Handler configured.")

  src_properties = {
    "web3_handler": node_connector,
    "actual_api_key": None,
    "consumer_txs_hash_ids": consumer_txs_hash_ids,
    "topic_txs_hash_ids": TOPIC_TXS_HASH_IDS,
  }

  sink_properties = {
    "api_keys_manager": api_keys_manager,
    "producer_txs_data": producer_txs_data,
    "topic_txs_data": TOPIC_TXS_DATA,
    "txs_threshold": TX_THROUGHPUT_THRESHOLD,
  }

  _ = (
    RawTransactionsProcessor(logger)
      .src_config(src_properties)
      .sink_config(sink_properties)
      .run(callback=handler_kafka.message_handler)
  )

