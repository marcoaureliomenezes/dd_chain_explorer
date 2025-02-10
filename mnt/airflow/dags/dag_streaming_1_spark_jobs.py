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

DOCKER_OP_COMMON_PARMS = dict(
  image="marcoaureliomenezes/spark-streaming-jobs:1.0.0",
  docker_url="unix:/var/run/docker.sock",
  auto_remove=True,
  tty=False,
  network_mode="vpc_dm",
)

DOCKER_SWARM_DEFAULT = dict(
  image="marcoaureliomenezes/spark-streaming-jobs:1.0.0",
  api_version='auto',
  networks=["vpc_dm"],
  docker_url="unix:/var/run/docker.sock",
  tty=False,
  enable_logging=True,
  auto_remove=True,
  force_pull=True,
  configs=["restart"],

)

LAKEHOUSE_ENV_VARS = dict(
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"),
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  S3_URL = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"),
  SPARK_URL = os.getenv("SPARK_URL"),
  KAFKA_BROKERS = os.getenv("KAFKA_BROKERS"),
  SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL"),
)


with DAG(
  f"pipeline_streaming_1_spark_jobs", 
  start_date=datetime(2024,7,20, 3), 
  schedule_interval="@once", 
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:


  starting_process = BashOperator(
    task_id="starting_task",
    bash_command="sleep 2")


  spark_app_multiplex_bronze = DockerOperator(
    **DOCKER_OP_COMMON_PARMS,
    task_id="spark_app_multiplex_bronze",
    entrypoint="sh /app/entrypoint.sh /app/pyspark/2_job_bronze_multiplex.py",
    environment=dict(
      **LAKEHOUSE_ENV_VARS,
      CHECKPOINT_PATH = "s3a://spark/checkpoints/iceberg/kafka_topics_multiplexed",
      TOPICS = "mainnet.1.mined_blocks.data,mainnet.2.orphan_blocks.data,mainnet.4.mined.txs.raw_data",
      CONSUMER_GROUP = "cg_bronze_1",
      STARTING_OFFSETS = "earliest",
      MAX_OFFSETS_PER_TRIGGER = 10000,
      TABLE_BRONZE = "nessie.bronze.kafka_topics_multiplexed"))


  spark_app_silver_blocks = DockerOperator(
    **DOCKER_OP_COMMON_PARMS,
    task_id="spark_app_silver_blocks",
    entrypoint="sh /app/entrypoint.sh /app/pyspark/3_job_silver_blocks.py",
    environment=dict(
      **LAKEHOUSE_ENV_VARS,
      CHECKPOINT_PATH = "s3a://spark/checkpoints/iceberg/blocks",
      TOPIC_BLOCKS = "mainnet.1.mined_blocks.data",
      TABLE_BRONZE = "nessie.bronze.kafka_topics_multiplexed",
      TABLE_SILVER_BLOCKS = "nessie.silver.blocks",
      TABLE_SILVER_BLOCKS_TXS = "nessie.silver.blocks_transactions"))


  # spark_app_silver_txs = DockerOperator(
  #   **DOCKER_OP_COMMON_PARMS,
  #   task_id="spark_app_silver_txs",
  #   entrypoint="sh /app/entrypoint.sh /app/pyspark/4_job_silver_transactions.py",
  #   environment=dict(
  #     **LAKEHOUSE_ENV_VARS,
  #     CHECKPOINT_PATH = "s3a://spark/checkpoints/iceberg/transactions",
  #     TOPIC_TXS = "mainnet.4.mined.txs.raw_data",
  #     TABLE_BRONZE = "nessie.bronze.kafka_topics_multiplexed",
  #     SILVER_TXS_P2P = "nessie.silver.transactions_p2p",
  #     SILVER_TXS_CONTRACTS = "nessie.silver.transactions_contracts",
  #     TABLE_SILVER_TXS = "nessie.silver.transactions",
  #     EXEC_MEMORY = "1g",
  #     NUM_EXECUTORS = "2",
  #     TOTAL_EXEC_CORES = "2"))


  test_docker_operator = DockerSwarmOperator(
    task_id="test_docker_operator",
    command="sh /app/entrypoint.sh /app/pyspark/4_job_silver_transactions.py",
    **DOCKER_SWARM_DEFAULT,
    environment=dict(
      **LAKEHOUSE_ENV_VARS,
      CHECKPOINT_PATH = "s3a://spark/checkpoints/iceberg/transactions",
      TOPIC_TXS = "mainnet.4.mined.txs.raw_data",
      TABLE_BRONZE = "nessie.bronze.kafka_topics_multiplexed",
      SILVER_TXS_P2P = "nessie.silver.transactions_p2p",
      SILVER_TXS_CONTRACTS = "nessie.silver.transactions_contracts",
      TABLE_SILVER_TXS = "nessie.silver.transactions",
      EXEC_MEMORY = "1g",
      NUM_EXECUTORS = "2",
      TOTAL_EXEC_CORES = "2")
    )

  starting_process >> spark_app_multiplex_bronze
  starting_process >> spark_app_silver_blocks
  starting_process >> test_docker_operator
