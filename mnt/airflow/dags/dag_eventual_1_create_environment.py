import os

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator


COMMON_DOCKER_OP = dict(
  network_mode="vpc_dm",
  docker_url="unix:/var/run/docker.sock",
  mount_tmp_dir=False,
  tty=False
)

LAKE_ENV_VARS = dict(
  SPARK_MASTER = os.getenv("SPARK_MASTER"),
  S3_URL = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"),
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"))

default_args ={
  "owner": "airflow",
  "email_on_failure": False,
  "email_on_retry": False,
  "email": "marco_aurelio_reis@yahoo.com.br",
  "retries": 1,
  "retry_delay": timedelta(minutes=5) 
}


with DAG(
  "pipeline_eventual_1_create_environment.py", 
  start_date=datetime(2025,2,1, 3), 
  schedule_interval="@once",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

  STARTING_TASK = BashOperator( task_id="STARTING_TASK", bash_command="""sleep 2""")


  CREATE_KAFKA_TOPICS = DockerOperator(
    image="marcoaureliomenezes/onchain-batch-txs:1.0.0",
    **COMMON_DOCKER_OP,
    task_id="CREATE_KAFKA_TOPICS",
    entrypoint="python -u /app/kafka_maintenance/0_create_topics.py /app/kafka_maintenance/conf/topics_dev.ini --overwrite false",
    environment = {
      "NETWORK": os.getenv("NETWORK"),
      "KAFKA_BROKERS": os.getenv("KAFKA_BROKERS")
    }
  )

  CREATE_BRONZE_TABLES = DockerOperator(
    image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
    **COMMON_DOCKER_OP,
    task_id="CREATE_BRONZE_TABLES",
    entrypoint="sh /app/entrypoint.sh /app/ddl_iceberg_tables/job_1_create_bronze_tables.py",
    environment= LAKE_ENV_VARS)


  CREATE_SILVER_BLOCKS_FAST = DockerOperator(
    image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
    **COMMON_DOCKER_OP,
    task_id="CREATE_SILVER_BLOCKS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/ddl_iceberg_tables/job_2_create_silver_tables_blocks.py",
    environment= LAKE_ENV_VARS)


  CREATE_SILVER_TXS_FAST = DockerOperator(
    image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
    **COMMON_DOCKER_OP,
    task_id="CREATE_SILVER_TXS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/ddl_iceberg_tables/job_3_create_silver_tables_txs.py",
    environment= LAKE_ENV_VARS)


  CREATE_SILVER_LOGS_FAST = DockerOperator(
    image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
    **COMMON_DOCKER_OP,
    task_id="CREATE_SILVER_LOGS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/ddl_iceberg_tables/job_4_create_silver_table_logs.py",
    environment= LAKE_ENV_VARS)
  

  FINAL_TASK = BashOperator( task_id="FINAL_TASK", bash_command="""sleep 2""")


  STARTING_TASK >> CREATE_BRONZE_TABLES >> CREATE_SILVER_BLOCKS_FAST >> FINAL_TASK
  STARTING_TASK >> CREATE_SILVER_TXS_FAST >> CREATE_SILVER_LOGS_FAST >> FINAL_TASK
  STARTING_TASK >> CREATE_KAFKA_TOPICS