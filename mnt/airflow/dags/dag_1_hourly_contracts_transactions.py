import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator

azure_conf = {
  "AZURE_SUBSCRIPTION_ID": os.getenv("AZURE_SUBSCRIPTION_ID"),
  "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
  "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
  "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
}


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
      docker_url="unix:/var/run/docker.sock",
      auto_remove=True,
      mount_tmp_dir=False,
      tty=False,
      network_mode="app_dev_network",
      image="marcoaureliomenezes/dm-onchain-batch-txs:1.0.0",
      task_id="capture_uniswap_v2_txs",
      entrypoint="python /app/job_data_capture.py",
      environment=dict(
        **azure_conf,
        AKV_VAULT_NAME = "DMEtherscanAsAService",
        API_KEY_NAME = "etherscan-api-key-2",
        NETWORK = "mainnet",
        HOST_HDFS = "http://namenode:9870",
        SCHEMA_REGISTRY_URL = "http://schema-registry:8081",
        KAFKA_BROKERS = "broker:29092",
        TOPIC_LOGS = "batch_application_logs",
        LAKE_PATH = "/raw/batch/contract_transactions",
        ADDRESS = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        END_DATE = "{{ execution_date }}"
        #END_DATE = os.getenv("END_DATE", "2024-08-24 12:00:00")
                             
      )
    )
    
    end_process = BashOperator(
      task_id="end_process",
      bash_command="""sleep 2"""
    )



    starting_process >> capture_uniswap_v2_txs >> end_process