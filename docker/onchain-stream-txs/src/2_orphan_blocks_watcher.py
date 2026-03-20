import json
import logging
import os

from logging import Logger
from typing import Dict, Any

from dm_chain_utils.dm_dynamodb import DMDynamoDB
from dm_chain_utils.dm_web3_client import Web3Handler
from dm_chain_utils.dm_sqs import SQSHandler
from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler


class OrphanBlocksProcessor:

  def __init__(self, logger: Logger):
    self.logger = logger

  def src_config(self, src_properties: Dict[str, Any]):
    self.handler_web3 = src_properties["handler_web3"]
    self.num_confirmations = src_properties["num_confirmations"]
    self.sqs_handler: SQSHandler = src_properties["sqs_handler"]
    self.sqs_queue_url = src_properties["sqs_queue_url"]
    return self

  def sink_config(self, sink_properties: Dict[str, Any]):
    self.block_cache: DMDynamoDB = sink_properties['block_cache']
    return self
  

  def recognize_orphaned_blocks(self, safe_block_number: int, safe_block_hash: str):
    item = self.block_cache.get_item("BLOCK_CACHE", str(safe_block_number))
    if item and item.get("block_hash") != safe_block_hash:
      return True
    return False

  def handle_orphaned_blocks_cache(self, mined_block: Dict, delay_counter: int) -> None:
    block_number = mined_block["value"]["block_number"]
    block_hash   = mined_block["value"]["block_hash"]

    # Persiste o bloco atual no DynamoDB com TTL de 1h
    self.block_cache.put_item(
      "BLOCK_CACHE", str(block_number),
      attrs={"block_hash": block_hash},
      ttl_seconds=3600,
    )


  def run(self):
    counter = 0
    delay_counter = 0
    for msg in self.sqs_handler.consume_queue(self.sqs_queue_url):
      mined_block = {"value": json.loads(msg["Body"])}
      self.sqs_handler.delete_message(self.sqs_queue_url, msg["ReceiptHandle"])
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
        value = {"block_timestamp": block_timestamp, "block_number": block_number, "block_hash": block_hash}
        # Re-enqueue orphan event so Job 3 re-processes the block
        self.sqs_handler.send_message(self.sqs_queue_url, json.dumps(value))
      else:
        if counter % 10 == 0:
          self.logger.info(f"Safe block {safe_block_number} confirmed")
      delay_counter = delay_counter + 1 if delay_counter < self.num_confirmations else self.num_confirmations
      counter += 1


if __name__ == "__main__":

  APP_NAME = "ORPHAN_BLOCKS_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  SSM_SECRET_NAME = os.getenv("SSM_SECRET_NAME")
  SQS_QUEUE_URL_MINED_BLOCKS = os.getenv("SQS_QUEUE_URL_MINED_BLOCKS")
  CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP")
  NUM_CONFIRMATIONS = int(os.getenv("NUM_CONFIRMATIONS", "10"))

  logging.basicConfig(level=logging.INFO, format='%(name)s — %(levelname)s — %(message)s')
  LOGGER = logging.getLogger(APP_NAME)

  # CloudWatch logging handler — replaces KafkaLoggingHandler
  LOGGER.addHandler(CloudWatchLoggingHandler(
    log_group=CLOUDWATCH_LOG_GROUP,
    log_stream=APP_NAME.lower(),
  ))
  LOGGER.info("CloudWatch logging handler configured.")

  # SQS handler — replaces Kafka Avro consumer/producer
  sqs_handler = SQSHandler(LOGGER)
  LOGGER.info("SQS handler configured.")

  handler_web3 = Web3Handler(LOGGER, NETWORK).get_node_connection(SSM_SECRET_NAME, 'alchemy')
  LOGGER.info("Blockchain Node Connection configured.")

  # Cache persistente de hashes de blocos — DynamoDB com TTL de 1h
  block_cache = DMDynamoDB(logger=LOGGER)
  LOGGER.info("DynamoDB block cache configured.")

  src_properties = {
    "handler_web3": handler_web3,
    "num_confirmations": NUM_CONFIRMATIONS,
    "sqs_handler": sqs_handler,
    "sqs_queue_url": SQS_QUEUE_URL_MINED_BLOCKS,
  }

  sink_properties = {
    "block_cache": block_cache,
  }

  BLOCK_MINER = (
    OrphanBlocksProcessor(LOGGER)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run()
  )