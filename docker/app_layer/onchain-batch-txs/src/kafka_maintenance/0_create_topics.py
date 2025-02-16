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
    parser.add_argument('--overwrite', type=str, default="false", help='Network')
    args = parser.parse_args()
    config = ConfigParser()
    config.read_file(args.config_file)
    overwrite = args.overwrite
    logger = logging.getLogger("KAFKA_ADMIN")
    logger.setLevel(logging.INFO)
    ConsoleLoggingHandler = ConsoleLoggingHandler()
    logger.addHandler(ConsoleLoggingHandler)
    kafka_conf = {"bootstrap.servers": "broker-1:29092"}
    kafka_admin = DMClusterAdmin(logger, kafka_conf)

    topics = [
      "topic.application.logs",
      "topic.batch.logs",
      "topic.mined_blocks.events",
      "topic.blocks_data",
      "topic.block_txs.hash_ids",
      "topic.txs.raw_data",
      "topic.txs.input_decoded"
    ]

    topic_configs = config["topic.general.config"]
    print(overwrite)
    for topic in topics:
      custom_configs = {**topic_configs, **config[topic]}
      topic_name, num_partitions, replication_factor = f"{NETWORK}.{custom_configs['name']}", int(custom_configs["num_partitions"]), int(custom_configs["replication_factor"])
      del custom_configs["name"]
      del custom_configs["num_partitions"]
      del custom_configs["replication_factor"]
      kafka_admin.create_topic(topic_name, num_partitions, replication_factor, custom_configs, overwrite=overwrite)

