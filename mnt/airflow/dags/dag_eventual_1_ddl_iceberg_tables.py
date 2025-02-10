import os

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator


COMMON_DOCKER_OP = dict(
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
  "pipeline_eventual_1_ddl_iceberg_tables", 
  start_date=datetime(2025,2,1, 3), 
  schedule_interval="@once",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

    starting_process = BashOperator(
      task_id="starting_task",
      bash_command="""sleep 2"""
    )


    create_table_bronze_multiplexed = DockerOperator(
      **COMMON_DOCKER_OP,
      task_id="create_table_bronze_multiplexed",
      entrypoint="sh /app/0_ddl_tables/entrypoint.sh /app/0_ddl_tables/job_1_create_b_multiplex.py",
      environment= {
        "TABLE_FULLNAME": "nessie.bronze.kafka_topics_multiplexed",
        **COMMON_SPARK_VARS
      }
    )

    create_table_silver_blocks = DockerOperator(
      **COMMON_DOCKER_OP,
      task_id="create_table_silver_blocks",
      entrypoint="sh /app/0_ddl_tables/entrypoint.sh /app/0_ddl_tables/job_2_create_s_blocks.py",
      environment= {
        "TABLE_FULLNAME": "nessie.silver.blocks",
        **COMMON_SPARK_VARS
      }
    )

    create_table_silver_blocks_transactions = DockerOperator(
      **COMMON_DOCKER_OP,
      task_id="create_table_silver_blocks_transactions",
      entrypoint="sh /app/0_ddl_tables/entrypoint.sh /app/0_ddl_tables/job_3_create_s_blocks_txs.py",
      environment= {
        "TABLE_FULLNAME": "nessie.silver.blocks_transactions",
        **COMMON_SPARK_VARS
      }
    )

    create_table_silver_transactions = DockerOperator(
      **COMMON_DOCKER_OP,
      task_id="create_table_silver_transactions",
      entrypoint="sh /app/0_ddl_tables/entrypoint.sh /app/0_ddl_tables/job_4_create_s_txs.py",
      environment= {
        "TABLE_FULLNAME": "nessie.silver.transactions",
        **COMMON_SPARK_VARS
      }
    )

    end_process = BashOperator(
      task_id="end_process",
      bash_command="""sleep 2"""
    )


    starting_process >> create_table_bronze_multiplexed >> create_table_silver_blocks >> create_table_silver_blocks_transactions >> create_table_silver_transactions >> end_process 