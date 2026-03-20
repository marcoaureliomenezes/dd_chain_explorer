import json
import logging
import os
import time
import uuid

from logging import Logger
from typing import Any, Dict

from requests import HTTPError
from dm_chain_utils.dm_dynamodb import DMDynamoDB
from dm_chain_utils.dm_web3_client import Web3Handler
from dm_chain_utils.dm_sqs import SQSHandler
from dm_chain_utils.dm_kinesis import KinesisHandler
from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler
from dm_chain_utils.api_keys_manager import APIKeysManager


class RawTransactionsProcessor:

  def __init__(self, logger: Logger):
    self.logger = logger

  def src_config(self, src_properties: Dict[str, Any]):
    self.sqs_handler: SQSHandler = src_properties['sqs_handler']
    self.sqs_queue_url = src_properties['sqs_queue_url']
    self.logger.info(f"Crawling transactions from SQS: {self.sqs_queue_url.split('/')[-1]}")
    self.web3 = src_properties["web3_handler"]
    self.actual_api_key = src_properties["actual_api_key"]
    return self


  def sink_config(self, sink_properties: Dict[str, Any]):
    self.api_keys_manager = sink_properties['api_keys_manager']
    self.kinesis_handler: KinesisHandler = sink_properties['kinesis_handler']
    self.kinesis_stream_txs = sink_properties['kinesis_stream_txs']
    return self

  def _send_to_dlq(self, tx_hash: str, reason: str) -> None:
    """Logs failed transactions. SQS DLQ handles redelivery automatically."""
    self.logger.warning(f"DLQ: tx {tx_hash} failed ({reason}).")

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
          try:
            actual_api_key = self._rotate_api_key(actual_api_key)
          except RuntimeError:
            # All keys are held in the DynamoDB semaphore simultaneously — deadlock.
            self.logger.error(f"Deadlock de API keys (semáforo cheio). Descartando tx {tx_hash}.")
            return None, actual_api_key
        else:
          self.logger.error(f"HTTPError inesperado buscando tx {tx_hash}: {err}")
          return None, actual_api_key
    self.logger.error(f"Todas as API keys rate-limited. Descartando tx {tx_hash}.")
    return None, actual_api_key
  

  def run(self) -> None:
    self.api_keys_manager.free_api_keys(free_timeout=0)
    actual_api_key = self.api_keys_manager.elect_new_api_key()
    self.web3.get_node_connection(actual_api_key, 'infura')
    self.api_keys_manager.check_api_key_request(actual_api_key)
    counter = 1
    self.txs_threshold = 100
    for msg in self.sqs_handler.consume_queue(self.sqs_queue_url):
      tx_hash = json.loads(msg["Body"])["tx_hash"]
      self.sqs_handler.delete_message(self.sqs_queue_url, msg["ReceiptHandle"])
      raw_transaction_data, actual_api_key = self._fetch_tx_with_rotation(tx_hash, actual_api_key)
      self.api_keys_manager.check_api_key_request(actual_api_key)
      if not raw_transaction_data:
        self._send_to_dlq(tx_hash, "api_exhausted")
        continue
      cleaned_transaction_data = self.web3.parse_transaction_data(raw_transaction_data)
      try:
        key = cleaned_transaction_data['hash']
        self.kinesis_handler.put_record(
          self.kinesis_stream_txs,
          data=json.dumps(cleaned_transaction_data, default=str),
          partition_key=key,
        )
      except Exception as e:
        self.logger.error(f"Error producing to Kinesis: {e}")

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
  NETWORK = os.getenv("NETWORK")
  CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP")
  SQS_QUEUE_URL_TXS_HASH_IDS = os.getenv("SQS_QUEUE_URL_TXS_HASH_IDS")
  KINESIS_STREAM_TRANSACTIONS = os.getenv("KINESIS_STREAM_TRANSACTIONS")
  API_KEY_NAMES = os.getenv("SSM_SECRET_NAMES")

  PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

  logging.basicConfig(level=logging.INFO, format='%(name)s — %(levelname)s — %(message)s')
  logger = logging.getLogger(APP_NAME)

  # CloudWatch logging handler — replaces KafkaLoggingHandler
  logger.addHandler(CloudWatchLoggingHandler(
    log_group=CLOUDWATCH_LOG_GROUP,
    log_stream=f"{APP_NAME.lower()}-{PROC_ID}",
  ))
  logger.info("CloudWatch logging handler configured.")

  sqs_handler = SQSHandler(logger)
  kinesis_handler = KinesisHandler(logger)
  logger.info("SQS and Kinesis handlers configured.")

  # DynamoDB — semáforo de API keys e contador de requisições (single-table)
  dynamodb = DMDynamoDB(logger=logger)
  api_keys_manager = APIKeysManager(logger, PROC_ID, dynamodb, API_KEY_NAMES)
  logger.info("API Keys Manager configured (DynamoDB).")

  # Web3 — conecta ao nó Infura via SSM
  node_connector = Web3Handler(logger, NETWORK)
  logger.info("Web3Handler configured.")

  src_properties = {
    "web3_handler": node_connector,
    "actual_api_key": None,
    "sqs_handler": sqs_handler,
    "sqs_queue_url": SQS_QUEUE_URL_TXS_HASH_IDS,
  }

  sink_properties = {
    "api_keys_manager": api_keys_manager,
    "kinesis_handler": kinesis_handler,
    "kinesis_stream_txs": KINESIS_STREAM_TRANSACTIONS,
  }

  _ = (
    RawTransactionsProcessor(logger)
      .src_config(src_properties)
      .sink_config(sink_properties)
      .run()
  )

