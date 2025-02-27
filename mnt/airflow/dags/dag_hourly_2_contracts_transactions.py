import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator

LAKE_ENV_VARS = dict(
  SPARK_MASTER = os.getenv("SPARK_MASTER"),
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"),
  S3_URL = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"))


COMMON_DOCKER_OP = dict(
  docker_url="unix:/var/run/docker.sock",
  auto_remove="force",
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
  f"pipeline_hourly_2_contracts_transactions",
  start_date=datetime(year=2025,month=2,day=13,hour=15),
  schedule_interval="@hourly",
  default_args=default_args,
  max_active_runs=2,
  catchup=True
  ) as dag:

    starting_process = BashOperator(
      task_id="starting_task",
      bash_command="""sleep 2"""
    )

    get_popular_contracts_addresses = DockerOperator(
      image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
      **COMMON_DOCKER_OP,
      network_mode="vpc_dm",
      task_id="get_popular_contracts_addresses",
      entrypoint="sh /app/entrypoint.sh /app/periodic_spark_processing/1_get_popular_contracts.py",
      environment= {
        **LAKE_ENV_VARS,
        "TABLE_NAME": "silver.transactions_fast",
        "REDIS_HOST": os.getenv("REDIS_HOST"),
        "REDIS_PORT": os.getenv("REDIS_PORT"),
        "REDIS_PASS": os.getenv("REDIS_PASS"),
        "REDIS_DB": "3"
      }
    )


    capture_and_ingest_popular_contracts_addresses_txs = DockerOperator(
      image="marcoaureliomenezes/onchain-batch-txs:1.0.0",
      **COMMON_DOCKER_OP,
      network_mode="vpc_dm",
      task_id="capture_and_ingest_popular_contracts_addresses_txs",
      entrypoint="python /app/batch_ingestion/1_capture_and_ingest_contracts_txs.py",
      environment= {
      "S3_URL": os.getenv("S3_URL"),
      "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
      "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
      "AWS_DEFAULT_REGION": os.getenv("AWS_DEFAULT_REGION"),
      "NETWORK": os.getenv("NETWORK"),
      "AZURE_SUBSCRIPTION_ID": os.getenv("AZURE_SUBSCRIPTION_ID"),
      "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
      "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
      "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
      "AKV_NAME": "DMEtherscanAsAService",
      "APK_NAME": "etherscan-api-key-2",
      "REDIS_HOST": os.getenv("REDIS_HOST"),
      "REDIS_PORT": os.getenv("REDIS_PORT"),
      "REDIS_PASS": os.getenv("REDIS_PASS"),
      "REDIS_DB": "3",
      "SCHEMA_REGISTRY_URL": os.getenv("SCHEMA_REGISTRY_URL"),
      "KAFKA_BROKERS": os.getenv("KAFKA_BROKERS"),
      "TOPIC_LOGS": "mainnet.0.application.logs",
      "S3_BUCKET": "raw-data",
      "S3_BUCKET_PREFIX": "contracts_transactions",
      "EXEC_DATE": "{{ execution_date }}"          
      }
    )


    bronze_popular_contracts_addresses_txs = DockerOperator(
      image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
      **COMMON_DOCKER_OP,
      network_mode="vpc_dm",
      task_id="bronze_popular_contracts_addresses_txs",
      entrypoint="sh /app/entrypoint.sh /app/periodic_spark_processing/2_ingest_txs_data_to_bronze.py",
      environment= {
        **LAKE_ENV_VARS,
        "REDIS_HOST": os.getenv("REDIS_HOST"),
        "REDIS_PORT": os.getenv("REDIS_PORT"),
        "REDIS_PASS": os.getenv("REDIS_PASS"),
        "REDIS_DB": "3",
        "TABLE_NAME": "bronze.popular_contracts_txs",
        "EXEC_DATE": "{{ execution_date }}"    
      }
    )

    starting_process >> get_popular_contracts_addresses >> capture_and_ingest_popular_contracts_addresses_txs >> bronze_popular_contracts_addresses_txs