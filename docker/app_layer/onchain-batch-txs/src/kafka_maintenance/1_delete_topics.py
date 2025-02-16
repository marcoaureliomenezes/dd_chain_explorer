import os
import logging
from argparse import ArgumentParser, FileType
from configparser import ConfigParser
from kafka_admin_client import DMClusterAdmin

from dm_33_utils.logger_utils import ConsoleLoggingHandler


if __name__ == "__main__":

    NETWORK = os.environ["NETWORK"]
    KAFKA_BROKER = os.getenv("KAFKA_BROKERS")
    parser = ArgumentParser(description=f'Stream transactions network')
    parser.add_argument('config_file', type=FileType('r'), help='Config file')
    parser.add_argument('--dry-run', type=str, default="true", help='Dry Run')
    args = parser.parse_args()
    config = ConfigParser()
    config.read_file(args.config_file)
    dry_run = args.dry_run

    logger = logging.getLogger("KAFKA_ADMIN")
    logger.setLevel(logging.INFO)
    ConsoleLoggingHandler = ConsoleLoggingHandler()
    logger.addHandler(ConsoleLoggingHandler)
    kafka_conf = {"bootstrap.servers": "broker-1:29092"}
    kafka_admin = DMClusterAdmin(logger, kafka_conf)

    topics = [
      # "topic.application.logs",
      # "topic.batch.logs",
      "topic.mined_blocks.events",
      "topic.blocks_data",
      "topic.block_txs.hash_ids",
      "topic.txs.raw_data",
      "topic.txs.input_decoded"
    ]

    print(dry_run)
    topic_configs = config["topic.general.config"]
    for topic in topics:
      topic_name = f"{NETWORK}.{config[topic]['name']}"
      kafka_admin.delete_topic(topic_name, dry_run=dry_run)


