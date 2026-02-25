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


with DAG(
    "dag_zn_test",
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

    test_docker_operator = DockerOperator(
        task_id="test_docker_operator",
        image="local/spark-stream-txs:latest",
        docker_url="unix:/var/run/docker.sock",
        auto_remove="force",
        network_mode="vpc_dm",
        mount_tmp_dir=False,
        tty=True,
        entrypoint="echo 'Airflow DockerOperator test OK'",
    )

    end_process = BashOperator(
        task_id="end_task",
        bash_command="sleep 2",
    )

    starting_process >> test_docker_operator >> end_process
