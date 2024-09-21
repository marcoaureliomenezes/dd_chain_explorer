# import os
# from datetime import datetime, timedelta
# from dotenv import load_dotenv
# from airflow import DAG
# from airflow.sensors.filesystem import FileSensor
# from airflow.operators.bash import BashOperator
# from airflow.operators.python import PythonOperator
# from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
# from airflow.providers.apache.hive.operators.hive import HiveOperator
# from airflow.hooks.base import BaseHook
# from airflow.providers.microsoft.azure.secrets.key_vault import AzureKeyVaultBackend



# default_args ={
#   "owner": "airflow",
#   "email_on_failure": False,
#   "email_on_retry": False,
#   "email": "marco_aurelio_reis@yahoo.com.br",
#   "retries": 1,
#   "retry_delay": timedelta(minutes=5) 
# }

# load_dotenv(".env")

# def get_secret(secret_name):
#     print(os.getenv("AZURE_CLIENT_ID"))
                                  

#     return 

# with DAG(
#             f"dag_2_ingestao_batch", 
#             start_date=datetime(2024,7,20, 3), 
#             schedule_interval="@hourly",
#             default_args=default_args,
#             max_active_runs=1,
#             catchup=False
#         ) as dag:


#     starting_process = BashOperator(
#         task_id="starting_task",
#         bash_command="""sleep 2"""
#     )


#     get_akv_secret = PythonOperator(
#         task_id="get_akv_secret",
#         python_callable=get_secret,
#         op_args=["etherscan-api-key-2"],
#         provide_context=True
#     )

#     # capture_data = PythonOperator(
#     #     task_id="capture_data",
#     #     python_callable=get_transactions,
#     #     op_args=["mainnet", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "DMEtherscanAsAService", "etherscan-api-key-2"],
#     #     provide_context=True
#     # )

#     # task_expurgate_data = PythonOperator(
#     #     task_id="task_expurgate_data",
#     #     python_callable=expurgate_data,
#     #     op_args=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
#     #     provide_context=True
#     # )


#     end_process = BashOperator(
#         task_id="end_process",
#         bash_command="""sleep 2"""
#     )

#     starting_process >> get_akv_secret >> capture_data >> task_expurgate_data >> end_process

