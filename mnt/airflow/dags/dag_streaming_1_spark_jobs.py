import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator


default_args = {
    "owner": "airflow",
    "email_on_failure": False,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

DOCKER_OP_COMMON_PARMS = dict(
    image="local/spark-stream-txs:latest",
    docker_url="unix:/var/run/docker.sock",
    auto_remove="force",
    tty=False,
    network_mode="vpc_dm",
)

LAKEHOUSE_ENV_VARS = dict(
    AWS_DEFAULT_REGION=os.getenv("AWS_DEFAULT_REGION"),
    AWS_REGION=os.getenv("AWS_REGION"),
    AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID"),
    AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY"),
    S3_URL=os.getenv("S3_URL"),
    KAFKA_BROKERS=os.getenv("KAFKA_BROKERS"),
    SCHEMA_REGISTRY_URL=os.getenv("SCHEMA_REGISTRY_URL"),
)

with DAG(
    "pipeline_streaming_1_spark_jobs",
    start_date=datetime(2024, 7, 20, 3),
    schedule_interval="@once",
    default_args=default_args,
    max_active_runs=1,
    catchup=False,
) as dag:

    starting_process = BashOperator(
        task_id="starting_task",
        bash_command="sleep 2",
    )

    spark_app_multiplex_bronze = DockerOperator(
        **DOCKER_OP_COMMON_PARMS,
        task_id="spark_app_multiplex_bronze",
        entrypoint="sh /app/entrypoint.sh /app/pyspark/2_job_bronze_multiplex.py",
        environment=dict(
            **LAKEHOUSE_ENV_VARS,
            CHECKPOINT_PATH="s3a://spark/checkpoints/kafka_topics_multiplexed",
            TOPICS="mainnet.1.mined_blocks.data,mainnet.2.orphan_blocks.data,mainnet.4.mined.txs.raw_data",
            CONSUMER_GROUP="cg_bronze_1",
            STARTING_OFFSETS="earliest",
            MAX_OFFSETS_PER_TRIGGER=10000,
        ),
    )

    spark_app_silver_blocks = DockerOperator(
        **DOCKER_OP_COMMON_PARMS,
        task_id="spark_app_silver_blocks",
        entrypoint="sh /app/entrypoint.sh /app/pyspark/3_job_silver_blocks.py",
        environment=dict(
            **LAKEHOUSE_ENV_VARS,
            CHECKPOINT_PATH="s3a://spark/checkpoints/blocks",
            TOPIC_BLOCKS="mainnet.1.mined_blocks.data",
        ),
    )

    spark_app_silver_txs = DockerOperator(
        **DOCKER_OP_COMMON_PARMS,
        task_id="spark_app_silver_txs",
        entrypoint="sh /app/entrypoint.sh /app/pyspark/4_job_silver_transactions.py",
        environment=dict(
            **LAKEHOUSE_ENV_VARS,
            CHECKPOINT_PATH="s3a://spark/checkpoints/transactions",
            TOPIC_TXS="mainnet.4.mined.txs.raw_data",
            EXEC_MEMORY="1g",
            NUM_EXECUTORS="2",
            TOTAL_EXEC_CORES="2",
        ),
    )

    spark_app_apk_consumption = DockerOperator(
        **DOCKER_OP_COMMON_PARMS,
        task_id="spark_app_apk_consumption",
        entrypoint="sh /app/entrypoint.sh /app/pyspark/5_job_apk_consumption_watcher.py",
        environment=dict(
            **LAKEHOUSE_ENV_VARS,
            TOPIC_APK="mainnet.0.application.logs",
            REDIS_HOST=os.getenv("REDIS_HOST"),
            REDIS_PORT=os.getenv("REDIS_PORT"),
            REDIS_PASS=os.getenv("REDIS_PASS"),
        ),
    )

    starting_process >> spark_app_multiplex_bronze
    starting_process >> spark_app_silver_blocks
    starting_process >> spark_app_silver_txs
    starting_process >> spark_app_apk_consumption
