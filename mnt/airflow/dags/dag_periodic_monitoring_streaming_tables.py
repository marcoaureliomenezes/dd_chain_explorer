import os
import redis

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python import PythonOperator
from python_scripts.restart_spark_streaming_drivers import SparkStreamingJobsHandler
  

  
COMMON_DOCKER_OP = dict(
  network_mode="vpc_dm",
  docker_url="unix:/var/run/docker.sock",
  auto_remove="force",
  mount_tmp_dir=False,
  tty=False,
)

LAKE_ENV_VARS = dict(
  SPARK_MASTER = os.getenv("SPARK_MASTER"),
  S3_URL = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"),
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"),
  EXEC_MEMORY= "2g",
  TOTAL_EXEC_CORES= "2")



default_args ={
  "owner": "airflow",
  "email_on_failure": False,
  "email_on_retry": False,
  "email": "marco_aurelio_reis@yahoo.com.br",
  "retries": 1,
  "retry_delay": timedelta(minutes=5) 
}




with DAG(
  "pipeline_periodic_monitoring_streaming_tables.py", 
  start_date=datetime(year=2025,month=2,day=14,hour=12),
  schedule_interval="*/15 * * * *",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

  STARTING_TASK = BashOperator( task_id="STARTING_TASK", bash_command="""sleep 2""")

  SEE_LATEST_MESSAGES_STREAMING_TABLES = DockerOperator(
    image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
    **COMMON_DOCKER_OP,
    task_id="SEE_LATEST_MESSAGES_STREAMING_TABLES",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/3_monitore_streaming.py",
    environment= {
      "TABLE_NAME": "silver.transactions_fast",
      "REDIS_HOST": os.getenv("REDIS_HOST"),
      "REDIS_PORT": os.getenv("REDIS_PORT"),
      "REDIS_PASS": os.getenv("REDIS_PASS"),
      "REDIS_DB": "3",
      **LAKE_ENV_VARS
    }
  )


  TAKING_ACTION_STREAMING_TABLES = PythonOperator(
    task_id="TAKING_ACTION_STREAMING_TABLES",
    python_callable=SparkStreamingJobsHandler().run,
    provide_context=True
  )

  STARTING_TASK >> SEE_LATEST_MESSAGES_STREAMING_TABLES >> TAKING_ACTION_STREAMING_TABLES