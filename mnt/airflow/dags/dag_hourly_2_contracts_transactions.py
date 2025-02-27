import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.docker.operators.docker import DockerOperator

from python_scripts.validate_cache_popular_contracts import PopularContractsCacheValidator
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

    STARTING_TASK = BashOperator(
      task_id="STARTING_TASK",
      bash_command="""sleep 2"""
    )


    VALIDATE_CACHE = BranchPythonOperator(
      task_id='VALIDATE_CACHE',
      python_callable=PopularContractsCacheValidator().run,
      op_args=["GET_POPULAR_CONTRACTS_AND_CACHE_IT", "BY_PASS"],
      provide_context=True)

    GET_POPULAR_CONTRACTS_AND_CACHE_THEM = DockerOperator(
      image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
      **COMMON_DOCKER_OP,
      network_mode="vpc_dm",
      task_id="GET_POPULAR_CONTRACTS_AND_CACHE_IT",
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

    BY_PASS_CACHE_FULLFILMENT = BashOperator(task_id="BY_PASS_CACHE_FULLFILMENT", bash_command='echo "BY_PASSING CACHE"' )

    CAPTURE_AND_STAGE_TXS_BY_CONTRACT = DockerOperator(
      image="marcoaureliomenezes/onchain-batch-txs:1.0.0",
      **COMMON_DOCKER_OP,
      network_mode="vpc_dm",
      task_id="CAPTURE_AND_STAGE_TXS_BY_CONTRACT",
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


    INGEST_TX_DATA_TO_BRONZE = DockerOperator(
      image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
      **COMMON_DOCKER_OP,
      network_mode="vpc_dm",
      task_id="INGEST_TX_DATA_TO_BRONZE",
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

    STARTING_TASK >> VALIDATE_CACHE >> [GET_POPULAR_CONTRACTS_AND_CACHE_THEM, BY_PASS_CACHE_FULLFILMENT] >> CAPTURE_AND_STAGE_TXS_BY_CONTRACT >> INGEST_TX_DATA_TO_BRONZE