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
  image="spark-batch-jobs:1.0.0",
  docker_url="unix:/var/run/docker.sock",
  auto_remove=True,
  network_mode="analytical_layer",
)

with DAG(
  f"dag_4_streaming_raw_bronze", 
  start_date=datetime(2024,7,20, 3), 
  schedule_interval="@once", 
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:


  starting_process = BashOperator(
    task_id="starting_task",
    bash_command="""sleep 2"""
  )

  raw_to_bronze_logs = DockerOperator(
    **DOCKER_OP_COMMON_PARMS,
    task_id="raw_to_bronze_logs",
    entrypoint="sh /app/1_job_raw_to_bronze_apps/spark_entrypoint.sh",
    environment=dict(
      APP_NAME="RAW_TO_BRONZE_APP_LOGS",
      PATH_RAW_DATA="hdfs://namenode:9000/raw/application_logs/mainnet.application.logs",
      BRONZE_TABLENAME="b_apps.app_logs",
      ODATETIME="{{ execution_date }}"
    )
  )

  raw_to_bronze_mined_blocks = DockerOperator(
    **DOCKER_OP_COMMON_PARMS,
    task_id="raw_to_bronze_mined_blocks",
    entrypoint="sh /app/2_job_raw_to_bronze_blocks/spark_entrypoint.sh",
    environment=dict(
      APP_NAME="RAW_TO_BRONZE_MINED_BLOCKS",
      PATH_RAW_DATA="hdfs://namenode:9000/raw/blocks/mainnet.mined.block.metadata",
      BRONZE_TABLENAME="b_blocks.mined_blocks"
    )
  )

  raw_to_bronze_mined_txs = DockerOperator(
    **DOCKER_OP_COMMON_PARMS,
    task_id="raw_to_bronze_mined_txs",
    entrypoint="sh /app/2_job_raw_to_bronze_blocks/spark_entrypoint.sh",
    environment=dict(
      APP_NAME="RAW_TO_BRONZE_MINED_TRANSACTIONS",
      PATH_RAW_DATA="hdfs://namenode:9000/raw/transactions/contract-call/mainnet.mined.txs.contract.call",
      BRONZE_TABLENAME="b_transactions.mined_transactions"
    )
  )

  end_process = BashOperator(
    task_id="end_task",
    bash_command="""sleep 2"""
  )


  starting_process >> raw_to_bronze_logs  >> raw_to_bronze_mined_blocks >> raw_to_bronze_mined_txs >> end_process
