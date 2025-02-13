import os

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator


COMMON_KWARGS_DOCKER_OPERATOR = dict(
  network_mode="vpc_dm",
  docker_url="unix:/var/run/docker.sock",
  auto_remove="force",
  mount_tmp_dir=False,
  tty=False,
)

COMMON_SPARK_VARS = dict(
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"),
  S3_URL = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"),
)

default_args ={
  "owner": "airflow",
  "email_on_failure": False,
  "email_on_retry": False,
  "email": "marco_aurelio_reis@yahoo.com.br",
  "retries": 1,
  "retry_delay": timedelta(minutes=5) 
}


with DAG(
  "pipeline_eventual_2_delete_environment", 
  start_date=datetime.now(),
  schedule_interval="@once",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:


    starting_process = BashOperator(
      task_id="starting_task",
      bash_command="""sleep 2"""
    )

    kafka_topics_creator = DockerOperator(
      image="marcoaureliomenezes/onchain-stream-txs:1.0.0",
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="topics_creator",
      entrypoint="python -u 0_topics_creator.py configs/topics_dev.ini",
      environment = {
        "NETWORK": os.getenv("NETWORK"),
        "KAFKA_BROKERS": os.getenv("KAFKA_BROKERS")
      }
    )


    delete_iceberg_tables_metadata = DockerOperator(
      image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="delete_iceberg_tables_metadata",
      entrypoint="sh /app/0_ddl_tables/entrypoint.sh /app/0_ddl_tables/job_5_delete_all_tables.py",
      environment= {
        "SPARK_MASTER": os.getenv("SPARK_MASTER"),
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "AWS_DEFAULT_REGION": os.getenv("AWS_DEFAULT_REGION"),
        "AWS_REGION": os.getenv("AWS_DEFAULT_REGION"),
        "S3_URL": os.getenv("S3_URL"),
        "NESSIE_URI": os.getenv("NESSIE_URI"),
      }
    )


    delete_iceberg_tables_data = DockerOperator(
      image="marcoaureliomenezes/onchain-batch-txs:1.0.0",
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="delete_iceberg_tables_data",
      entrypoint="python 4_delete_keys_s3.py --bucket lakehouse",
      environment= {
        "TOPIC_LOGS": "mainnet.0.application.logs",
        "MODE": "ALL",
        **COMMON_SPARK_VARS
      }
    )


    delete_spark_streaming_checkpoints = DockerOperator(
      image="marcoaureliomenezes/onchain-batch-txs:1.0.0",
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="delete_spark_streaming_checkpoints",
      entrypoint="python 4_delete_keys_s3.py --bucket spark",
      environment= {
        "TOPIC_LOGS": "mainnet.0.application.logs",
        "MODE": "ALL",
        **COMMON_SPARK_VARS
      }
    )



    starting_process >> kafka_topics_creator
    starting_process >>  delete_iceberg_tables_metadata >> delete_iceberg_tables_data >> delete_spark_streaming_checkpoints