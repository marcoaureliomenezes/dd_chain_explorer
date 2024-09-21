import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.apache.hive.operators.hive import HiveOperator
from airflow.hooks.base import BaseHook
from airflow.providers.microsoft.azure.secrets.key_vault import AzureKeyVaultBackend
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
  f"dag_0_jobs_eventuais", 
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
      hql="CREATE DATABASE IF NOT EXISTS b_apps",
      hive_cli_conn_id="hive-conn"
    )


    create_icetable_app_logs = HiveOperator(
      task_id="create_icetable_app_logs",
      hql=create_table_b_apps_app_logs("b_apps.app_logs", "hdfs://namenode:9000/dm_lakehouse/bronze/b_apps/app_logs"),
      hive_cli_conn_id="hive-conn"
    )


    create_database_b_blocks = HiveOperator(
      task_id="create_database_b_blocks",
      hql="CREATE DATABASE IF NOT EXISTS b_blocks",
      hive_cli_conn_id="hive-conn"
    )


    create_icetable_mined_blocks = HiveOperator(
      task_id="create_icetable_mined_blocks",
      hql=create_table_b_blocks_mined_blocks("b_blocks.mined_blocks", "hdfs://namenode:9000/dm_lakehouse/bronze/b_blocks/mined_blocks"),
      hive_cli_conn_id="hive-conn"
    )


    create_database_b_transactions = HiveOperator(
      task_id="create_database_b_transactions",
      hql="CREATE DATABASE IF NOT EXISTS b_transactions",
      hive_cli_conn_id="hive-conn"
    )

    create_icetable_mined_txs = HiveOperator(
      task_id="create_icetable_mined_txs",
      hql=create_table_b_blocks_mined_txs(
          "b_transactions.mined_transactions", 
          "hdfs://namenode:9000/dm_lakehouse/bronze/b_transactions/mined_transactions"),
      hive_cli_conn_id="hive-conn"
    )

    end_process = BashOperator(
      task_id="end_process",
      bash_command="""sleep 2"""
    )



    starting_process >> create_database_b_apps >> create_icetable_app_logs >> end_process
    starting_process >> create_database_b_blocks >> create_icetable_mined_blocks >> end_process    
    starting_process >> create_database_b_transactions >> create_icetable_mined_txs >> end_process

