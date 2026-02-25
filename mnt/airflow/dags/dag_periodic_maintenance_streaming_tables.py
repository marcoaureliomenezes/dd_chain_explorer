import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator


default_args = {
    "owner": "airflow",
    "email_on_failure": False,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    "pipeline_periodic_maintenance_streaming_tables",
    start_date=datetime(year=2025, month=2, day=24, hour=12),
    schedule_interval="0 */12 * * *",
    default_args=default_args,
    max_active_runs=1,
    catchup=True,
) as dag:

    STARTING_TASK = BashOperator(task_id="STARTING_TASK", bash_command="sleep 2")

    RUN_MAINTENANCE = DatabricksRunNowOperator(
        task_id="RUN_MAINTENANCE",
        databricks_conn_id="databricks_default",
        job_name=f"{os.getenv('DATABRICKS_JOB_NAME_PREFIX', '')}[dev] dm-iceberg-maintenance",
    )

    FINAL_TASK = BashOperator(task_id="FINAL_TASK", bash_command="sleep 2")

    STARTING_TASK >> RUN_MAINTENANCE >> FINAL_TASK
