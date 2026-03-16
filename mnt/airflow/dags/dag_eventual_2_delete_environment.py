import configparser
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from python_scripts.alerts import slack_alert


def _read_aws_env() -> dict:
    """Return AWS credential dict.

    Prefers explicit env vars (CI/CD, ECS task role, etc.).
    Falls back to parsing ~/.aws/credentials when running with a mounted
    credentials file (local dev setup).
    """
    key_id = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not key_id or not secret:
        try:
            cfg = configparser.ConfigParser()
            cfg.read(os.path.expanduser("~/.aws/credentials"))
            profile = os.getenv("AWS_PROFILE", "default")
            key_id = cfg.get(profile, "aws_access_key_id", fallback=None)
            secret = cfg.get(profile, "aws_secret_access_key", fallback=None)
        except Exception:
            pass
    return {
        "AWS_ACCESS_KEY_ID":     key_id,
        "AWS_SECRET_ACCESS_KEY": secret,
        "AWS_DEFAULT_REGION":    os.getenv("AWS_DEFAULT_REGION"),
        "AWS_REGION":            os.getenv("AWS_REGION"),
        "S3_URL":                os.getenv("S3_URL"),
    }


COMMON_DOCKER_OP = dict(
    network_mode="vpc_dm",
    docker_url="unix:/var/run/docker.sock",
    auto_remove="force",
    mount_tmp_dir=False,
    tty=False,
    force_pull=False,   # imagens locais — não tentar pull de registry
)

COMMON_SPARK_VARS = _read_aws_env()

default_args = {
    "owner": "airflow",
    "email_on_failure": True,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": slack_alert,
}


with DAG(
    "pipeline_eventual_2_delete_environment",
    start_date=datetime.now(),
    schedule_interval="@once",
    default_args=default_args,
    max_active_runs=1,
    catchup=False,
) as dag:

    starting_process = BashOperator(
        task_id="starting_task",
        bash_command="sleep 2",
    )

    delete_kafka_topics = DockerOperator(
        image="local/onchain-batch-txs:latest",
        **COMMON_DOCKER_OP,
        task_id="delete_kafka_topics",
        entrypoint="python -u /app/kafka_maintenance/1_delete_topics.py /app/kafka_maintenance/conf/topics_dev.ini --dry-run true",
        environment={
            "NETWORK": os.getenv("NETWORK"),
            "KAFKA_BROKERS": os.getenv("KAFKA_BROKERS"),
        },
    )

    delete_s3_raw_data = DockerOperator(
        image="local/onchain-batch-txs:latest",
        **COMMON_DOCKER_OP,
        task_id="delete_s3_raw_data",
        entrypoint=(
            f"python /app/s3_maintenance/1_delete_s3_objects.py"
            f" --bucket {os.getenv('DEV_S3_BUCKET', 'dm-chain-explorer-dev-ingestion')}"
            f" --prefix bronze/kafka_multiplex/"
        ),
        environment={
            "TOPIC_LOGS": "mainnet.0.application.logs",
            "MODE": "ALL",
            **COMMON_SPARK_VARS,
        },
    )

    delete_spark_streaming_checkpoints = DockerOperator(
        image="local/onchain-batch-txs:latest",
        **COMMON_DOCKER_OP,
        task_id="delete_spark_streaming_checkpoints",
        entrypoint=(
            f"python /app/s3_maintenance/1_delete_s3_objects.py"
            f" --bucket {os.getenv('DEV_S3_BUCKET', 'dm-chain-explorer-dev-ingestion')}"
            f" --prefix spark-checkpoints/"
        ),
        environment={
            "TOPIC_LOGS": "mainnet.0.application.logs",
            "MODE": "ALL",
            **COMMON_SPARK_VARS,
        },
    )

    cleanup_dynamodb = DockerOperator(
        image="local/onchain-batch-txs:latest",
        **COMMON_DOCKER_OP,
        task_id="cleanup_dynamodb",
        entrypoint="python",
        command=[
            "-c",
            (
                "import boto3; "
                "import os; "
                "table_name = os.getenv('DYNAMODB_TABLE', 'dm-chain-explorer'); "
                "dynamodb = boto3.resource('dynamodb'); "
                "table = dynamodb.Table(table_name); "
                "resp = table.scan(ProjectionExpression='pk, sk'); "
                "items = resp.get('Items', []); "
                "print(f'Deleting {len(items)} items from {table_name}'); "
                "[table.delete_item(Key={'pk': i['pk'], 'sk': i['sk']}) for i in items]; "
                "print('DynamoDB cleanup complete')"
            ),
        ],
        environment={
            "DYNAMODB_TABLE": os.getenv("DYNAMODB_TABLE", "dm-chain-explorer"),
            **COMMON_SPARK_VARS,
        },
    )

    FINAL_TASK = BashOperator(task_id="FINAL_TASK", bash_command="sleep 2")

    DELETE_DATABRICKS_TABLES = DatabricksRunNowOperator(
        task_id="DELETE_DATABRICKS_TABLES",
        databricks_conn_id="databricks_default",
        job_name=f"{os.getenv('DATABRICKS_JOB_NAME_PREFIX', '')}dm-teardown",
    )

    starting_process >> delete_kafka_topics >> FINAL_TASK
    starting_process >> delete_s3_raw_data >> delete_spark_streaming_checkpoints >> FINAL_TASK
    starting_process >> DELETE_DATABRICKS_TABLES >> FINAL_TASK
    starting_process >> cleanup_dynamodb >> FINAL_TASK
