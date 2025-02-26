import os
import redis

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python import PythonOperator

import docker
from docker import DockerClient
from docker.models.services import Service
from typing import TypeVar
from requests.models import Response


class DockerHandler:

  def __init__(self):
    self.client: DockerClient = docker.from_env()

  def list_containers_names(self):
    stacks = self.client.containers.list()
    stacks = [stack.name for stack in stacks]
    return stacks


  def list_services(self):
    services = self.client.services.list()
    services = [service.name for service in services]
    return services

  def list_stack_services(self, stack_name):
    services = self.client.services.list(filters={"label": f"com.docker.stack.namespace={stack_name}"})
    services = [service.name for service in services]
    return services

  def list_stack_names(self):
    services = self.client.services.list()
    stacks = set()
    for service in services:
      stack_name = service.attrs["Spec"]["Labels"].get("com.docker.stack.namespace")
      if stack_name:
        stacks.add(stack_name)
    return stacks

  def list_containers(self):
    containers = self.client.containers.list()
    containers = [container.name for container in containers]
    return containers

  def restart_service(self, service_name):
    service = self.client.services.get(service_name)
    service.force_update()
    return
    

  

  
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


def get_latest_messages():

  map_spark_apps = {
    'newst_mined_blocks_events': 'layer_spark_apps_spark-app-silver-mined-blocks-events',
    'newst_apps_logs_fast': 'layer_spark_apps_spark-app-silver-logs',
    'newst_blocks_fast': 'layer_spark_apps_spark-app-silver-blocks',
    'newst_transactions_fast': 'layer_spark_apps_spark-app-silver-txs'
  }
  dt_now = datetime.now()
  #'layer_spark_apps_spark-app-multiplex-bronze', 'layer_spark_apps_spark-app-apk-comsumption']

  redis_client = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=5, password=os.getenv("REDIS_PASS"), decode_responses=True)
  data = list(map(lambda key: (key, redis_client.get(key)), redis_client.keys()))
  data = {i: datetime.strptime(j, "%Y-%m-%d %H:%M:%S") for i, j in data}
  
  data_delta = {i: (dt_now - j).total_seconds() for i, j in data.items()}
  data_late = {i: j for i, j in data_delta.items() if j > 900}
  services_to_restart = list(data_late.keys())
  print(services_to_restart)
  docker_client = DockerHandler()
  services = docker_client.list_services()
  print("SERVICES ALL ", services)
  for service in services_to_restart:
    service_name = map_spark_apps.get(service)
    if service_name:
      print(f"RESTARTING {service_name}")
      docker_client.restart_service(service_name)
  return "DONE"


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
    python_callable=get_latest_messages,
    provide_context=True
  )

  STARTING_TASK >> SEE_LATEST_MESSAGES_STREAMING_TABLES >> TAKING_ACTION_STREAMING_TABLES