import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from docker.types import Mount


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
# HOST_HOME é o $HOME do host (ex: /home/marco), injetado via compose.
# O DockerOperator conversa com o daemon do host via docker.sock, então os
# caminhos de mount são resolvidos no filesystem do HOST, não do container.
_HOST_HOME = os.getenv("HOST_HOME", os.path.expanduser("~"))

COMMON_DOCKER_OP = dict(
    image="local/onchain-batch-txs:latest",
    network_mode="vpc_dm",
    docker_url="unix:/var/run/docker.sock",
    force_pull=False,
    mount_tmp_dir=False,
    tty=False,
    auto_remove="force",   # remove container após execução (sucesso ou falha)
    mounts=[
        # Credenciais AWS do host → boto3/SSM conseguem autenticar
        Mount(source=f"{_HOST_HOME}/.aws", target="/root/.aws", type="bind", read_only=True),
    ],
)

with DAG(
    "pipeline_hourly_2_contracts_transactions",
    start_date=datetime(year=2026, month=3, day=1),
    schedule_interval="@hourly",
    default_args=default_args,
    max_active_runs=1,   # evita merges Silver concorrentes para a mesma ingestion_date
    catchup=False,       # não reprocessar histórico; apenas a próxima janela agendada
) as dag:

    STARTING_TASK = BashOperator(task_id="STARTING_TASK", bash_command="sleep 2")

    # ── Job 1: Docker → Etherscan → S3 raw (batch/) ───────────────────────────
    FETCH_CONTRACTS_TXS = DockerOperator(
        task_id="FETCH_CONTRACTS_TXS",
        entrypoint="python -u /app/batch_ingestion/1_capture_and_ingest_contracts_txs.py",
        environment={
            # Python path: o script vive em /app/batch_ingestion/ mas importa de /app/utils/
            "PYTHONPATH":           "/app",
            # Janela temporal: EXEC_DATE = fim da hora (end_date da janela de 1h)
            "EXEC_DATE":            "{{ data_interval_end.strftime('%Y-%m-%d %H:%M:%S+0000') }}",
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
    # notebook_params precisa estar dentro de `json` pois apenas o campo `json`
    # está em template_fields do DatabricksRunNowOperator (v6.7.0).
    LOAD_BRONZE_CONTRACTS_TXS = DatabricksRunNowOperator(
        task_id="LOAD_BRONZE_CONTRACTS_TXS",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}dm-batch-s3-to-bronze",
        json={
            "notebook_params": {
                "exec_date":  "{{ data_interval_end.strftime('%Y-%m-%dT%H') }}",
                "catalog":    "dev",
                "s3_bucket":  DEV_S3_BUCKET,
                "s3_prefix":  S3_BATCH_PREFIX,
            }
        },
    )

    # ── Job 3: Databricks — Bronze → Silver transactions_batch ───────────────
    PROCESS_SILVER_CONTRACTS_TXS = DatabricksRunNowOperator(
        task_id="PROCESS_SILVER_CONTRACTS_TXS",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}dm-batch-bronze-to-silver",
        json={
            "notebook_params": {
                "exec_date": "{{ data_interval_end.strftime('%Y-%m-%dT%H') }}",
                "catalog":   "dev",
            }
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
