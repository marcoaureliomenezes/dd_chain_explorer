import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker_swarm import DockerSwarmOperator
from airflow.providers.docker.operators.docker import DockerOperator


default_args ={
  "owner": "airflow",
  "email_on_failure": False,
  "email_on_retry": False,
  "email": "marco_aurelio_reis@yahoo.com.br",
  "retries": 1,
  "retry_delay": timedelta(minutes=5) 
}


with DAG(
  f"dag_n_test", 
  start_date=datetime(2024,7,20, 3), 
  schedule_interval="@once", 
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:


  starting_process = BashOperator(
    task_id="starting_task",
    bash_command="""sleep 2"""
  )

  test_docker_swarm_operator = DockerSwarmOperator(
    api_version='auto',
    task_id='test_docker_swarm_operator',
    image='centos:latest',
    command='/bin/sleep 45',
    auto_remove=True,
    tty=True,
    networks=["layer_batch_prod"],
    docker_url="unix:/var/run/docker.sock",
    enable_logging=True
  )

  test_docker_operator = DockerOperator(
    task_id="test_docker_operator",
    image="spark-batch-jobs:1.0.0",
    docker_url="unix:/var/run/docker.sock",
    auto_remove=True,
    network_mode="layer_batch_prod",
    mount_tmp_dir=False,
    tty=True,
    environment=dict(
      APP_NAME="RAW_TO_BRONZE_MINED_BLOCKS",
      PATH_RAW_DATA="hdfs://namenode:9000/raw/blocks/mainnet.mined.block.metadata",
      BRONZE_TABLENAME="b_blocks.mined_blocks"
    ),
    entrypoint="sh /app/2_job_raw_to_bronze_blocks/spark_entrypoint.sh",
  )

  end_process = BashOperator(
    task_id="end_task",
    bash_command="""sleep 2"""
  )


  starting_process >> test_docker_swarm_operator >> end_process
  starting_process >> test_docker_operator >> end_process
