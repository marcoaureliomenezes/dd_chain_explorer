import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.docker.operators.docker_swarm import DockerSwarmOperator

default_args ={
  "owner": "airflow",
  "email_on_failure": False,
  "email_on_retry": False,
  "email": "marco_aurelio_reis@yahoo.com.br",
  "retries": 1,
  "retry_delay": timedelta(minutes=5) 
}

with DAG(
  "dag_3_streaming_raw_crawlers", 
  start_date=datetime(2024,7,20, 3), 
  schedule_interval="@once", 
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

  starting_process = BashOperator(
    task_id="starting_task",
    bash_command="""sleep 2"""
  )

  # <<: *common_conf
  #   env_file:
  #     - ./conf/.secrets.conf


  general_conf = dict(
    docker_url="unix:/var/run/docker.sock",
    auto_remove=True,
    mount_tmp_dir=False,
    tty=False,
    network_mode="app_dev_network",
  )

  mined_blocks_crawler = DockerOperator(
    **general_conf,
    image="marcoaureliomenezes/dm-onchain-stream-txs:1.0.0",
    task_id="mined_blocks_crawler",
    entrypoint="python -u 1_mined_blocks_crawler.py configs/producers.ini",
    environment=dict(
      AKV_SECRET_NAME = 'alchemy-api-key-1',
      KAFKA_BROKERS = 'broker:29092',
      NETWORK="mainnet",
      SCHEMA_REGISTRY_URL="http://schema-registry:8081",
      TOPIC_LOGS="mainnet.application.logs",
      TOPIC_MINED_BLOCKS="mainnet.mined.block.metadata",
      TOPIC_TXS_HASH_IDS="mainnet.mined.txs.hash.id",
      AKV_NODE_NAME="DataMasterNodeAsAService",
      TOPIC_TXS_HASH_IDS_PARTITIONS="8",
      CLOCK_FREQUENCY="1",
      TXS_PER_BLOCK="80"
    )
  )

  orphan_blocks_crawler = DockerOperator(
    **general_conf,
    image="marcoaureliomenezes/dm-onchain-stream-txs:1.0.0",
    task_id="orphan_blocks_crawler",
    entrypoint="python -u 2_orphan_blocks_crawler.py configs/producers.ini configs/consumers.ini",
    environment=dict(
    )
  )

  redis_collector = DockerOperator(
    **general_conf,
    image="marcoaureliomenezes/dm-onchain-stream-txs:1.0.0",
    task_id="redis_collector",
    entrypoint="python -u n_semaphore_collect.py",
    environment=dict(
    )
  )

  redis_collector = DockerOperator(
    **general_conf,
    image="marcoaureliomenezes/dm-onchain-stream-txs:1.0.0",
    task_id="redis_collector",
    entrypoint="python -u n_semaphore_collect.py",
    environment=dict(
      REDIS_HOST='redis',
      REDIS_PORT='6379',
      FREQUENCY=0.5
    )
  )

  api_keys_log_processor = DockerOperator(
    **general_conf,
    task_id="api_keys_log_processor",
    image="marcoaureliomenezes/dm-spark-streaming-jobs:1.0.0",
    entrypoint="sh /app/1_api_key_monitor/spark_entrypoint.sh",
    environment=dict(
    )
  )


  starting_process >> mined_blocks_crawler
  
  starting_process >> orphan_blocks_crawler
