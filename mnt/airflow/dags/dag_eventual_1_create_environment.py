import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator


COMMON_DOCKER_OP = dict(
    network_mode="vpc_dm",
    docker_url="unix:/var/run/docker.sock",
    mount_tmp_dir=False,
    tty=False,
    force_pull=False,   # imagens locais — não tentar pull de registry
)

LAKE_ENV_VARS = dict(
    SPARK_MASTER=os.getenv("SPARK_MASTER"),
    S3_URL=os.getenv("S3_URL"),
    AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID"),
    AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY"),
    AWS_DEFAULT_REGION=os.getenv("AWS_DEFAULT_REGION"),
    AWS_REGION=os.getenv("AWS_REGION"),
)

default_args = {
    "owner": "airflow",
    "email_on_failure": False,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    "pipeline_eventual_1_create_environment",
    start_date=datetime(2025, 2, 1, 3),
    schedule_interval="@once",
    default_args=default_args,
    max_active_runs=1,
    catchup=False,
) as dag:

    STARTING_TASK = BashOperator(task_id="STARTING_TASK", bash_command="sleep 2")

    CREATE_KAFKA_TOPICS = DockerOperator(
        image="local/onchain-batch-txs:latest",
        **COMMON_DOCKER_OP,
        task_id="CREATE_KAFKA_TOPICS",
        entrypoint="python -u /app/kafka_maintenance/0_create_topics.py /app/kafka_maintenance/conf/topics_dev.ini --overwrite false",
        environment={
            "NETWORK": os.getenv("NETWORK"),
            "KAFKA_BROKERS": os.getenv("KAFKA_BROKERS"),
        },
    )

    FINAL_TASK = BashOperator(task_id="FINAL_TASK", bash_command="sleep 2")

    CREATE_DATABRICKS_TABLES = DatabricksRunNowOperator(
        task_id="CREATE_DATABRICKS_TABLES",
        databricks_conn_id="databricks_default",
        job_name=f"{os.getenv('DATABRICKS_JOB_NAME_PREFIX', '')}[dev] dm-ddl-setup",
    )

    STARTING_TASK >> CREATE_KAFKA_TOPICS >> CREATE_DATABRICKS_TABLES >> FINAL_TASK
