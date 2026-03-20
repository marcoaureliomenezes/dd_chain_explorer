import json
import logging
import os

from logging import Logger
from typing import Dict, List, Any

from dm_chain_utils.dm_web3_client import Web3Handler
from dm_chain_utils.dm_sqs import SQSHandler
from dm_chain_utils.dm_kinesis import KinesisHandler
from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler


class BlockDataCrawler:


  def __init__(self, logger: Logger):
    self.logger = logger


  def src_config(self, src_properties: Dict[str, Any]):
    self.handler_web3 = src_properties["handler_web3"]
    self.sqs_handler: SQSHandler = src_properties["sqs_handler"]
    self.sqs_queue_url_mined_blocks = src_properties["sqs_queue_url_mined_blocks"]
    self.logger.info("SQS consumer for mined blocks events configured.")
    return self


  def sink_config(self, sink_properties: Dict[str, Any]):
    self.kinesis_handler: KinesisHandler = sink_properties['kinesis_handler']
    self.kinesis_stream_blocks = sink_properties['kinesis_stream_blocks']
    self.sqs_handler_sink: SQSHandler = sink_properties['sqs_handler_sink']
    self.sqs_queue_url_txs_hash_ids = sink_properties['sqs_queue_url_txs_hash_ids']
    self.txs_threshold = sink_properties['txs_threshold']
    return self
      

  def batch_txs_hash_ids(self, txs_list: List[str]):
    txs_list = txs_list[:self.txs_threshold] if self.txs_threshold else txs_list
    entries = [{"MessageBody": json.dumps({"tx_hash": h})} for h in txs_list]
    if entries:
      self.sqs_handler_sink.send_message_batch(self.sqs_queue_url_txs_hash_ids, entries)


  def run(self) -> None:
    for msg in self.sqs_handler.consume_queue(self.sqs_queue_url_mined_blocks):
      block_event = json.loads(msg["Body"])
      self.sqs_handler.delete_message(self.sqs_queue_url_mined_blocks, msg["ReceiptHandle"])
      block_data = self.handler_web3.extract_block_data(block_event["block_number"])
      cleaned_data = self.handler_web3.parse_block_data(block_data)
      key = str(cleaned_data['number'])
      # Produce block data to Kinesis (→ Firehose → S3)
      self.kinesis_handler.put_record(
        self.kinesis_stream_blocks,
        data=json.dumps(cleaned_data, default=str),
        partition_key=key,
      )
      self.batch_txs_hash_ids(txs_list=cleaned_data["transactions"])
      self.logger.info(f"Ingestion;STREAM:{self.kinesis_stream_blocks};NUM_TXS:{len(cleaned_data['transactions'])};BLOCK:{key}")
  

if __name__ == '__main__':

  APP_NAME = "BLOCK_DATA_CRAWLER"
  NETWORK = os.getenv("NETWORK")
  SSM_SECRET_NAME = os.getenv("SSM_SECRET_NAME")
  CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP")
  SQS_QUEUE_URL_MINED_BLOCKS = os.getenv("SQS_QUEUE_URL_MINED_BLOCKS")
  SQS_QUEUE_URL_TXS_HASH_IDS = os.getenv("SQS_QUEUE_URL_TXS_HASH_IDS")
  KINESIS_STREAM_BLOCKS = os.getenv("KINESIS_STREAM_BLOCKS")
  TXS_PER_BLOCK = int(os.getenv("TXS_PER_BLOCK", "0"))

  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  logger = logging.getLogger(APP_NAME)

  # CloudWatch logging handler — replaces KafkaLoggingHandler
  logger.addHandler(CloudWatchLoggingHandler(
    log_group=CLOUDWATCH_LOG_GROUP,
    log_stream=APP_NAME.lower(),
  ))
  logger.info("CloudWatch logging handler configured.")

  sqs_handler = SQSHandler(logger)
  kinesis_handler = KinesisHandler(logger)
  logger.info("SQS and Kinesis handlers configured.")

  # Blockchain node connection via SSM
  handler_web3 = Web3Handler(logger, NETWORK).get_node_connection(SSM_SECRET_NAME, 'alchemy')
  logger.info("Blockchain node connection configured.")

  src_properties = {
    "handler_web3": handler_web3,
    "sqs_handler": sqs_handler,
    "sqs_queue_url_mined_blocks": SQS_QUEUE_URL_MINED_BLOCKS,
  }

  sink_properties = {
    "kinesis_handler": kinesis_handler,
    "kinesis_stream_blocks": KINESIS_STREAM_BLOCKS,
    "sqs_handler_sink": sqs_handler,
    "sqs_queue_url_txs_hash_ids": SQS_QUEUE_URL_TXS_HASH_IDS,
    "txs_threshold": TXS_PER_BLOCK,
  }

  logger.info("Starting Block Data Crawler")
  _ = (
    BlockDataCrawler(logger)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run()
  )
