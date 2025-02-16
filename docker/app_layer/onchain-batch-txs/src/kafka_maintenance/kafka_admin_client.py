import time
from logging import Logger
from typing import Dict, Any
from confluent_kafka.admin import AdminClient, NewTopic


class DMClusterAdmin:

  def __init__(self, logger: Logger, cluster_conf: Dict[str, Any]):
    self.logger = logger
    self.kafka_admin = AdminClient(conf=cluster_conf)


  def list_topics(self):
    cluster_metadata = self.kafka_admin.list_topics()
    topics = cluster_metadata.topics.keys()
    return [topic for topic in topics if not topic.startswith("_")]

  def check_if_topic_exists(self, topic: str):
    return topic in self.list_topics()

  def delete_topic(self, topic_name: str, dry_run: str= "true"):
    if dry_run == "true":
      self.logger.info(f"Topic {topic_name} 'deleted' [mode dry-run] with success!")
      return
    self.kafka_admin.delete_topics([topic_name])
    self.logger.info(f"Topic {topic_name} deleted with success!")
    time.sleep(2)

  
  def create_topic(self, name: str, num_partitions: int, replication_factor: int, topic_configs={}, overwrite: bool=False):
    if overwrite == "true": self.delete_topic(name, dry_run="false")
    if (overwrite == "false") and (self.check_if_topic_exists(name)):
      self.logger.info(f"Topic {name} already exists and you are not overwriting it")
      return
    topic = NewTopic(name, num_partitions, replication_factor, config=topic_configs)
    self.kafka_admin.create_topics(new_topics=[topic], validate_only=False)
    self.logger.info(f"Topic {name} created with success!")