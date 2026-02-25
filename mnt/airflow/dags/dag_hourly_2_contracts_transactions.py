import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator


default_args = {
    "owner": "airflow",
    "email_on_failure": False,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

JOB_PREFIX     = os.getenv("DATABRICKS_JOB_NAME_PREFIX", "")
DEV_S3_BUCKET  = os.getenv("DEV_S3_BUCKET", "dm-chain-explorer-dev-ingestion")
S3_BATCH_PREFIX = os.getenv("S3_BATCH_PREFIX", "batch")

# Env vars injetados no container Docker (Job 1)
# Atenção: valores None são descartados pelo SDK Docker → defaults seguros
COMMON_DOCKER_OP = dict(
    image="local/onchain-batch-txs:latest",
    network_mode="vpc_dm",
    docker_url="unix:/var/run/docker.sock",
    force_pull=False,
    mount_tmp_dir=False,
    tty=False,
)

with DAG(
    "pipeline_hourly_2_contracts_transactions",
    start_date=datetime(year=2025, month=2, day=13, hour=15),
    schedule_interval="@hourly",
    default_args=default_args,
    max_active_runs=2,
    catchup=True,
) as dag:

    STARTING_TASK = BashOperator(task_id="STARTING_TASK", bash_command="sleep 2")

    # ── Job 1: Docker → Etherscan → S3 raw (batch/) ───────────────────────────
    FETCH_CONTRACTS_TXS = DockerOperator(
        task_id="FETCH_CONTRACTS_TXS",
        entrypoint="python -u /app/batch_ingestion/1_capture_and_ingest_contracts_txs.py",
        environment={
            # Janela temporal: EXEC_DATE = fim da hora (end_date da janela de 1h)
            "EXEC_DATE":            "{{ next_execution_date.strftime('%Y-%m-%d %H:%M:%S+0000') }}",
            # S3
            "S3_BUCKET":            DEV_S3_BUCKET,
            "S3_BUCKET_PREFIX":     S3_BATCH_PREFIX,
            # Rede / Kafka / Schema Registry
            "NETWORK":              os.getenv("NETWORK"),
            "KAFKA_BROKERS":        os.getenv("KAFKA_BROKERS"),
            "SCHEMA_REGISTRY_URL":  os.getenv("SCHEMA_REGISTRY_URL"),
            "TOPIC_LOGS":           os.getenv("TOPIC_LOGS", ""),
            # Redis — contratos populares (DB3, sem senha em DEV)
            "REDIS_HOST":           os.getenv("REDIS_HOST", "redis"),
            "REDIS_PORT":           os.getenv("REDIS_PORT", "6379"),
            "REDIS_PASS":           os.getenv("REDIS_PASS", ""),
            "REDIS_DB":             os.getenv("REDIS_DB_CONTRACTS", "3"),
            # AWS
            "AWS_DEFAULT_REGION":   os.getenv("AWS_DEFAULT_REGION", "sa-east-1"),
        },
        **COMMON_DOCKER_OP,
    )

    # ── Job 2: Databricks — S3 → Bronze popular_contracts_txs ────────────────
    LOAD_BRONZE_CONTRACTS_TXS = DatabricksRunNowOperator(
        task_id="LOAD_BRONZE_CONTRACTS_TXS",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}[dev] dm-batch-s3-to-bronze",
        notebook_params={
            "exec_date":  "{{ next_execution_date.strftime('%Y-%m-%dT%H') }}",
            "catalog":    "dev",
            "s3_bucket":  DEV_S3_BUCKET,
            "s3_prefix":  S3_BATCH_PREFIX,
        },
    )

    # ── Job 3: Databricks — Bronze → Silver transactions_batch ───────────────
    PROCESS_SILVER_CONTRACTS_TXS = DatabricksRunNowOperator(
        task_id="PROCESS_SILVER_CONTRACTS_TXS",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}[dev] dm-batch-bronze-to-silver",
        notebook_params={
            "exec_date": "{{ next_execution_date.strftime('%Y-%m-%dT%H') }}",
            "catalog":   "dev",
        },
    )

    FINAL_TASK = BashOperator(task_id="FINAL_TASK", bash_command="sleep 2")

    (
        STARTING_TASK
        >> FETCH_CONTRACTS_TXS
        >> LOAD_BRONZE_CONTRACTS_TXS
        >> PROCESS_SILVER_CONTRACTS_TXS
        >> FINAL_TASK
    )
