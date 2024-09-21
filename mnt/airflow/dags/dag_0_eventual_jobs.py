from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.apache.hive.operators.hive import HiveOperator
from hive_ddls.create_tables import (
    create_table_b_apps_app_logs,
    create_table_b_blocks_mined_blocks,
    create_table_b_blocks_mined_txs,
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
  "dag_0_eventual_jobs", 
  start_date=datetime(2024,7,20, 3), 
  schedule_interval="@once",
  default_args=default_args,
  max_active_runs=1,
  catchup=False) as dag:

    starting_process = BashOperator(
      task_id="starting_task",
      bash_command="""sleep 2"""
    )
    
    create_database_b_apps = HiveOperator(
      task_id="create_database_b_apps",
      hive_cli_conn_id="hive-conn",
      hql="CREATE DATABASE IF NOT EXISTS b_apps",
    )

    create_database_b_blocks = HiveOperator(
      task_id="create_database_b_blocks",
      hive_cli_conn_id="hive-conn",
      hql="CREATE DATABASE IF NOT EXISTS b_blocks"
    )

    create_database_b_transactions = HiveOperator(
      task_id="create_database_b_transactions",
      hive_cli_conn_id="hive-conn",
      hql="CREATE DATABASE IF NOT EXISTS b_transactions"
    )

    create_table_app_logs = HiveOperator(
      task_id="create_table_app_logs",
      hive_cli_conn_id="hive-conn",
      hql=create_table_b_apps_app_logs(
        "b_apps.app_logs",
        "hdfs://namenode:9000/dm_lakehouse/bronze/b_apps/app_logs"
      )
    )

    create_table_mined_blocks = HiveOperator(
      task_id="create_table_mined_blocks",
      hive_cli_conn_id="hive-conn",
      hql=create_table_b_blocks_mined_blocks(
        "b_blocks.mined_blocks",
        "hdfs://namenode:9000/dm_lakehouse/bronze/b_blocks/mined_blocks"
      )
    )

    create_table_mined_txs = HiveOperator(
      task_id="create_table_mined_txs",
      hive_cli_conn_id="hive-conn",
      hql=create_table_b_blocks_mined_txs(
        "b_transactions.mined_transactions", 
        "hdfs://namenode:9000/dm_lakehouse/bronze/b_transactions/mined_transactions"
      )
    )

    end_process = BashOperator(
      task_id="end_process",
      bash_command="""sleep 2"""
    )

    starting_process >> create_database_b_apps >> create_table_app_logs >> end_process
    starting_process >> create_database_b_blocks >> create_table_mined_blocks >> end_process    
    starting_process >> create_database_b_transactions >> create_table_mined_txs >> end_process