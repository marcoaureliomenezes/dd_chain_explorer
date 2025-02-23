import os

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.docker.operators.docker import DockerOperator


COMMON_KWARGS_DOCKER_OPERATOR = dict(
  image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
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


def should_run_full_process(job, dummy, **kwargs):
  return job if kwargs['execution_date'].hour % 24 == 0 else dummy,
      


with DAG(
  "pipeline_periodic_monitoring_streaming_tables.py", 
  start_date=datetime(year=2025,month=2,day=14,hour=12),
  schedule_interval="0 */6 * * *",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

  STARTING_TASK = BashOperator( task_id="STARTING_TASK", bash_command="""sleep 2""")

  REWRITE_FILES_0001= DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_FILES_0001",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/1_rewrite_data_files.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "silver.blocks" })
