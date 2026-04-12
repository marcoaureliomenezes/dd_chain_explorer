import json
import logging
import os
import time

from logging import Logger
from typing import Dict, Generator, Callable, Any

from dm_chain_utils.dm_web3_client import Web3Handler
from dm_chain_utils.dm_sqs import SQSHandler
from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler


class MinedBlocksWatcher:

  def __init__(self, logger: Logger):
    self.logger = logger


  def src_config(self, src_properties: Dict[str, Any]):
    self.handler_web3 = src_properties["handler_web3"]
    return self


  def sink_config(self, sink_properties: Dict[str, Any]):
    self.sqs_handler = sink_properties['sqs_handler']
    self.sqs_queue_url = sink_properties['sqs_queue_url']
    return self
  

  def extract_stream(self, frequency: int) -> Generator:
    prev_block_number = 0
    while True:
      actual_block = self.handler_web3.extract_block_data()
      if actual_block:
        actual_block_number = actual_block.get('number')
        if actual_block_number > prev_block_number:
          # Emit ALL blocks from prev+1 to actual_block_number (inclusive).
          # When ≥2 blocks are mined between polls (common — avg blocktime 12s),
          # fetch each missed block individually to prevent silent data loss.
          for bn in range(prev_block_number + 1, actual_block_number):
            missed_block = self.handler_web3.extract_block_data(bn)
            if missed_block:
              yield missed_block
            else:
              self.logger.warning(f"Block {bn} unavailable at fetch time; will be reconciled by job_reconcile_orphans")
          yield actual_block  # already fetched — emit last
          prev_block_number = actual_block_number
      time.sleep(float(frequency))
      

  def run(self, frequency: int) -> None:
    for block_data in self.extract_stream(frequency):
      block_timestamp = block_data['timestamp']
      block_number = block_data['number']
      block_hash = bytes.hex(block_data['hash'])

      value = {"block_timestamp": block_timestamp, "block_number": block_number, "block_hash": block_hash}
      self.sqs_handler.send_message(self.sqs_queue_url, json.dumps(value))
      LOGGER.info(f"Block Mined;{value}")
      print(f"Block Mined;{value}")
  




if __name__ == '__main__':

  APP_NAME = "MINED_BLOCKS_EVENTS"
  NETWORK = os.getenv("NETWORK")
  SQS_QUEUE_URL_MINED_BLOCKS = os.getenv("SQS_QUEUE_URL_MINED_BLOCKS")
  CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP")
  SSM_SECRET_NAME = os.getenv('SSM_SECRET_NAME')
  CLOCK_FREQUENCY = float(os.getenv("CLOCK_FREQUENCY"))

  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  LOGGER = logging.getLogger(APP_NAME)

  # CloudWatch logging handler — replaces KafkaLoggingHandler
  LOGGER.addHandler(CloudWatchLoggingHandler(
    log_group=CLOUDWATCH_LOG_GROUP,
    log_stream=APP_NAME.lower(),
  ))
  LOGGER.info("CloudWatch logging handler configured.")

  # SQS handler — replaces Kafka Avro producer
  sqs_handler = SQSHandler(LOGGER)
  LOGGER.info("SQS handler configured.")

  handler_web3 = Web3Handler(LOGGER, NETWORK).get_node_connection(SSM_SECRET_NAME, 'alchemy')
  LOGGER.info("Blockchain Node Connection configured.")

  src_properties = {"handler_web3": handler_web3}
  sink_properties = {
    "sqs_handler": sqs_handler,
    "sqs_queue_url": SQS_QUEUE_URL_MINED_BLOCKS,
  }

  LOGGER.info("Starting Mined Blocks Processor")
  _ = (
     MinedBlocksWatcher(LOGGER)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(CLOCK_FREQUENCY)
  )
