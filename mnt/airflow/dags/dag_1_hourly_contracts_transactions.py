import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator



COMMON_ENV_VARS = {
  "AZURE_SUBSCRIPTION_ID": os.getenv("AZURE_SUBSCRIPTION_ID"),
  "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
  "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
  "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
  "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
  "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
  "S3_URL": os.getenv("S3_URL"),
  "SR_URL": os.getenv("SR_URL"),
  "KAFKA_BROKERS": os.getenv("KAFKA_BROKERS"),
  "NETWORK": os.getenv("NETWORK"),
  "AKV_NAME": "DMEtherscanAsAService",
  "S3_BUCKET": "/raw/batch/contract_transactions",
  "TOPIC_LOGS": "batch_application_logs",
}

COMMON_DOCKER_OP = dict(
  image="marcoaureliomenezes/onchain-batch-txs:1.0.0",
  docker_url="unix:/var/run/docker.sock",
  auto_remove=True,
  mount_tmp_dir=False,
  tty=False,
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
  f"dag_1_hourly_contracts_transactions",
  start_date=datetime(year=2024,month=7,day=20,hour=2),
  schedule_interval="@hourly",
  default_args=default_args,
  max_active_runs=2,
  catchup=True
  ) as dag:

    starting_process = BashOperator(
      task_id="starting_task",
      bash_command="""sleep 2"""
    )

    capture_uniswap_v2_txs = DockerOperator(
      **COMMON_DOCKER_OP,
      network_mode="ice_lakehouse_dev",
      task_id="capture_uniswap_v2_txs",
      entrypoint="python /app/job_data_capture.py",
      environment= {
      **COMMON_ENV_VARS,
      "APK_NAME": "etherscan-api-key-2",
      "ADDRESS": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
      "END_DATE": "{{ execution_date }}"                      
      }
    )
    
    end_process = BashOperator(
      task_id="end_process",
      bash_command="""sleep 2"""
    )



    starting_process >> capture_uniswap_v2_txs >> end_process