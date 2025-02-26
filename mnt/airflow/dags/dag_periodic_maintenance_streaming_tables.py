import os

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.docker.operators.docker import DockerOperator


COMMON_KWARGS_DOCKER_OPERATOR = dict(
  image="marcoaureliomenezes/spark-batch-jobs:1.0.0",
  network_mode="vpc_dm",
  docker_url="unix:/var/run/docker.sock",
  auto_remove="force",
  mount_tmp_dir=False,
  tty=False,
)

LAKE_ENV_VARS = dict(
  SPARK_MASTER = os.getenv("SPARK_MASTER"),
  S3_URL = os.getenv("S3_URL"),
  NESSIE_URI = os.getenv("NESSIE_URI"),
  AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID"),
  AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY"),
  AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION"),
  AWS_REGION = os.getenv("AWS_REGION"),
  EXEC_MEMORY= "2g",
  TOTAL_EXEC_CORES= "2")



default_args ={
  "owner": "airflow",
  "email_on_failure": False,
  "email_on_retry": False,
  "email": "marco_aurelio_reis@yahoo.com.br",
  "retries": 1,
  "retry_delay": timedelta(minutes=5) 
}


def should_run_full_process(job, dummy, **kwargs):
  return job if kwargs['execution_date'].hour % 24 == 0 else dummy,
      

with DAG(
  "pipeline_periodic_maintenance_streaming_tables.py", 
  start_date=datetime(year=2025,month=2,day=24,hour=12),
  schedule_interval="0 */12 * * *",
  default_args=default_args,
  max_active_runs=1,
  catchup=True) as dag:

  STARTING_TASK = BashOperator( task_id="STARTING_TASK", bash_command="""sleep 2""")

  ######################################################################################################################
  ###########################     TASKS FOR MAINTENANCE OF BLOCKS_EVENTS TABLE    ######################################
  ######################################################################################################################

  REWRITE_FILES_BLOCKS_EVENTS = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_FILES_BLOCKS_EVENTS",
    trigger_rule='one_success',
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/1_rewrite_data_files.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.mined_blocks_events" })

  BRANCH_OPER_BLOCKS_EVENTS = BranchPythonOperator(
    task_id='BRANCH_OPER_BLOCKS_EVENTS',
    python_callable=should_run_full_process,
    op_args=["REWRITE_EXPIRE_MANIFESTS_BLOCKS_EVENTS", "DUMMY_OPER_BLOCKS_EVENTS"],
    provide_context=True)
  
  DUMMY_OPER_BLOCKS_EVENTS = BashOperator(
    task_id="DUMMY_OPER_BLOCKS_EVENTS",
    bash_command="""sleep 2""")
  
  REWRITE_EXPIRE_MANIFESTS_BLOCKS_EVENTS = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_EXPIRE_MANIFESTS_BLOCKS_EVENTS",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/2_rewrite_and_expire_manifests.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.mined_blocks_events", "HOURS_RETAIN": 24, "MIN_SNAPSHOTS": 5 })

  ######################################################################################################################
  #############################    TASKS FOR MAINTENANCE OF BLOCKS_FAST TABLE    #######################################
  ######################################################################################################################

  REWRITE_FILES_BLOCKS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_FILES_BLOCKS_FAST",
    trigger_rule='one_success',
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/1_rewrite_data_files.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.blocks_fast" })

  BRANCH_OPER_BLOCKS_FAST = BranchPythonOperator(
    task_id='BRANCH_OPER_BLOCKS_FAST',
    python_callable=should_run_full_process,
    op_args=["REWRITE_EXPIRE_MANIFESTS_BLOCKS_FAST", "DUMMY_OPER_BLOCKS_FAST"],
    provide_context=True)

  DUMMY_OPER_BLOCKS_FAST = BashOperator( task_id="DUMMY_OPER_BLOCKS_FAST", bash_command="""sleep 2""")

  REWRITE_EXPIRE_MANIFESTS_BLOCKS_FAST= DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_EXPIRE_MANIFESTS_BLOCKS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/2_rewrite_and_expire_manifests.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.blocks_fast", "HOURS_RETAIN": 24, "MIN_SNAPSHOTS": 5 })
  
  ######################################################################################################################
  ############################    TASKS FOR MAINTENANCE OF BLOCKS_TXS_FAST TABLE    ####################################
  ######################################################################################################################

  REWRITE_FILES_BLOCKS_TXS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_FILES_BLOCKS_TXS_FAST",
    trigger_rule='one_success',
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/1_rewrite_data_files.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.blocks_txs_fast" })

  BRANCH_OPER_BLOCKS_TXS_FAST = BranchPythonOperator(
    task_id='BRANCH_OPER_BLOCKS_TXS_FAST',
    python_callable=should_run_full_process,
    op_args=["REWRITE_EXPIRE_MANIFESTS_BLOCKS_TXS_FAST", "DUMMY_OPER_BLOCKS_TXS_FAST"],
    provide_context=True)

  DUMMY_OPER_BLOCKS_TXS_FAST = BashOperator(task_id="DUMMY_OPER_BLOCKS_TXS_FAST", bash_command="""sleep 2""")

  REWRITE_EXPIRE_MANIFESTS_BLOCKS_TXS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_EXPIRE_MANIFESTS_BLOCKS_TXS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/2_rewrite_and_expire_manifests.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.blocks_txs_fast", "HOURS_RETAIN": 24, "MIN_SNAPSHOTS": 5 })

  ######################################################################################################################
  ##############################    TASKS FOR MAINTENANCE OF TXS_FAST TABLE    #########################################
  ######################################################################################################################

  REWRITE_FILES_TXS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_FILES_TXS_FAST",
    trigger_rule='one_success',
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/1_rewrite_data_files.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.transactions_fast" })

  BRANCH_OPER_TXS_FAST = BranchPythonOperator(
    task_id='BRANCH_OPER_TXS_FAST',
    python_callable=should_run_full_process,
    op_args=["REWRITE_EXPIRE_MANIFESTS_TXS_FAST", "DUMMY_OPER_TXS_FAST"],
    provide_context=True)
  
  DUMMY_OPER_TXS_FAST = BashOperator(
    task_id="DUMMY_OPER_TXS_FAST",
    bash_command="""sleep 2""")
  
  REWRITE_EXPIRE_MANIFESTS_TXS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_EXPIRE_MANIFESTS_TXS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/2_rewrite_and_expire_manifests.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_apps.transactions_fast", "HOURS_RETAIN": 24, "MIN_SNAPSHOTS": 5 })
  
  ######################################################################################################################
  ######################     TASKS FOR MAINTENANCE OF BLOCKS_EVENTS TABLE    ###########################################
  ######################################################################################################################
  
  REWRITE_FILES_APP_LOGS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_FILES_APP_LOGS_FAST",
    trigger_rule='one_success',
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/1_rewrite_data_files.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_logs.apps_logs_fast" })

  BRANCH_OPER_LOGS_FAST = BranchPythonOperator(
    task_id='BRANCH_OPER_LOGS_FAST',
    python_callable=should_run_full_process,
    op_args=["REWRITE_EXPIRE_MANIFESTS_APP_LOGS_FAST", "DUMMY_OPER_APP_LOGS_FAST"],
    provide_context=True)

  DUMMY_OPER_APP_LOGS_FAST = BashOperator(
    task_id="DUMMY_OPER_APP_LOGS_FAST",
    bash_command="""sleep 2""")
  
  REWRITE_EXPIRE_MANIFESTS_APP_LOGS_FAST = DockerOperator(
    **COMMON_KWARGS_DOCKER_OPERATOR,
    task_id="REWRITE_EXPIRE_MANIFESTS_APP_LOGS_FAST",
    entrypoint="sh /app/entrypoint.sh /app/maintenance_streaming_tables/2_rewrite_and_expire_manifests.py",
    environment= { **LAKE_ENV_VARS, "TABLE_FULLNAME": "s_logs.apps_logs_fast", "HOURS_RETAIN": 24, "MIN_SNAPSHOTS": 5 })
  
  FINAL_TASK = BashOperator( task_id="FINAL_TASK", trigger_rule='one_success', bash_command="""sleep 2""")

  #############################################################################################################################################################################
  ##############################################                    CONDITIONS                 ################################################################################
  #############################################################################################################################################################################

  STARTING_TASK >> REWRITE_FILES_BLOCKS_EVENTS >> BRANCH_OPER_BLOCKS_EVENTS >> [DUMMY_OPER_BLOCKS_EVENTS, REWRITE_EXPIRE_MANIFESTS_BLOCKS_EVENTS] >> REWRITE_FILES_BLOCKS_FAST
  REWRITE_FILES_BLOCKS_FAST >> BRANCH_OPER_BLOCKS_FAST >> [DUMMY_OPER_BLOCKS_FAST, REWRITE_EXPIRE_MANIFESTS_BLOCKS_FAST] >> REWRITE_FILES_BLOCKS_TXS_FAST
  REWRITE_FILES_BLOCKS_TXS_FAST >> BRANCH_OPER_BLOCKS_TXS_FAST >> [DUMMY_OPER_BLOCKS_TXS_FAST, REWRITE_EXPIRE_MANIFESTS_BLOCKS_TXS_FAST] >> REWRITE_FILES_TXS_FAST
  REWRITE_FILES_TXS_FAST >> BRANCH_OPER_TXS_FAST >> [DUMMY_OPER_TXS_FAST, REWRITE_EXPIRE_MANIFESTS_TXS_FAST] >> REWRITE_FILES_APP_LOGS_FAST
  REWRITE_FILES_APP_LOGS_FAST >> BRANCH_OPER_LOGS_FAST >> [DUMMY_OPER_APP_LOGS_FAST, REWRITE_EXPIRE_MANIFESTS_APP_LOGS_FAST] >> FINAL_TASK
  
  #############################################################################################################################################################################
  ##############################################                    END OF PIPELINE                 ###########################################################################