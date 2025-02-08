import os

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator


COMMON_KWARGS_DOCKER_OPERATOR = dict(
  image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
  network_mode="vpc_dm",
  docker_url="unix:/var/run/docker.sock",
  auto_remove=True,
  mount_tmp_dir=False,
  tty=False,
)

COMMON_SPARK_VARS = dict(
  S3_ENDPOINT = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"),
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"),
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
  "pipeline_hourly_1_maintenance_ice_streaming", 
  start_date=datetime(year=2025,month=2,day=2,hour=19),
  schedule_interval="@hourly",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

    starting_process = BashOperator(
      task_id="starting_task",
      bash_command="""sleep 2"""
    )


    maintenance_bronze_multiplexed = DockerOperator(
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="maintenance_bronze_multiplexed",
      entrypoint="sh /app/1_iceberg_maintenance/entrypoint.sh /app/1_iceberg_maintenance/maintenance_ice_tables.py",
      environment= {
        "TABLE_FULLNAME": "nessie.bronze.kafka_topics_multiplexed",
        **COMMON_SPARK_VARS
      }
    )

    maintenance_silver_blocks= DockerOperator(
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="maintenance_silver_blocks",
      entrypoint="sh /app/1_iceberg_maintenance/entrypoint.sh /app/1_iceberg_maintenance/maintenance_ice_tables.py",
      environment= {
        "TABLE_FULLNAME": "nessie.silver.blocks",
        **COMMON_SPARK_VARS
      }
    )

    maintenance_silver_blocks_transactions = DockerOperator(
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="maintenance_silver_blocks_transactions",
      entrypoint="sh /app/1_iceberg_maintenance/entrypoint.sh /app/1_iceberg_maintenance/maintenance_ice_tables.py",
      environment= {
        "TABLE_FULLNAME": "nessie.silver.blocks_transactions",
        **COMMON_SPARK_VARS
      }
    )

    maintenance_silver_transactions = DockerOperator(
      **COMMON_KWARGS_DOCKER_OPERATOR,
      task_id="maintenance_silver_transactions",
      entrypoint="sh /app/1_iceberg_maintenance/entrypoint.sh /app/1_iceberg_maintenance/maintenance_ice_tables.py",
      environment= {
        "TABLE_FULLNAME": "nessie.silver.transactions",
        **COMMON_SPARK_VARS
      }
    )

    end_process = BashOperator(
      task_id="end_process",
      bash_command="""sleep 2"""
    )


    starting_process >> maintenance_bronze_multiplexed >> maintenance_silver_blocks >> maintenance_silver_blocks_transactions >> maintenance_silver_transactions >> end_process