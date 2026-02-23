"""
Deleta e recria apenas o tópico de logs de aplicação.

Uso:
  python 2_recreate_logs_topic.py conf/topics_dev.ini

Útil para:
- Limpar mensagens de logs com formato de chave obsoleto (pré-migração SSM hierárquico).
- Forçar o job Spark (api_key_monitor) a iniciar do zero após recriar o tópico.
"""
import os
import logging
import time
from argparse import ArgumentParser, FileType
from configparser import ConfigParser

from kafka_admin_client import DMClusterAdmin
from dm_33_utils.logger_utils import ConsoleLoggingHandler


if __name__ == "__main__":

    NETWORK = os.environ["NETWORK"]
    KAFKA_BROKER = os.getenv("KAFKA_BROKERS")

    parser = ArgumentParser(description="Delete + recreate the application logs topic")
    parser.add_argument("config_file", type=FileType("r"), help="topics ini config file")
    args = parser.parse_args()

    config = ConfigParser()
    config.read_file(args.config_file)

    logger = logging.getLogger("KAFKA_RECREATE_LOGS")
    logger.setLevel(logging.INFO)
    logger.addHandler(ConsoleLoggingHandler())

    kafka_conf = {"bootstrap.servers": KAFKA_BROKER}
    kafka_admin = DMClusterAdmin(logger, kafka_conf)

    section = "topic.application.logs"
    topic_name = f"{NETWORK}.{config[section]['name']}"
    num_partitions = int(config[section]["num_partitions"])
    replication_factor = int(config[section]["replication_factor"])
    topic_configs = {
        k: v
        for k, v in {**config["topic.general.config"], **config[section]}.items()
        if k not in ("name", "num_partitions", "replication_factor")
    }

    logger.info(f"Deleting topic '{topic_name}'...")
    kafka_admin.delete_topic(topic_name, dry_run="false")

    logger.info("Waiting 3s for deletion to propagate...")
    time.sleep(3)

    logger.info(f"Recreating topic '{topic_name}' (partitions={num_partitions}, rf={replication_factor})...")
    kafka_admin.create_topic(topic_name, num_partitions, replication_factor, topic_configs, overwrite="false")

    logger.info(f"Topic '{topic_name}' recreated successfully.")
