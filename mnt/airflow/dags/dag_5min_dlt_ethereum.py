import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator


default_args = {
    "owner": "airflow",
    "email_on_failure": False,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

# Prefixo injetado pelo Airflow via compose (ex: "[dev marcoaurelioreislima] ")
JOB_PREFIX = os.getenv("DATABRICKS_JOB_NAME_PREFIX", "")

with DAG(
    "pipeline_5min_dlt_pipelines",
    start_date=datetime(year=2026, month=3, day=8),
    schedule_interval="*/5 * * * *",
    default_args=default_args,
    max_active_runs=1,   # Evita runs concorrentes: se o pipeline ainda está rodando
                         # quando o próximo slot disparar, o Airflow simplesmente
                         # aguarda sem enfileirar um novo run.
    catchup=False,
    tags=["databricks", "dlt", "streaming"],
    doc_md="""
## pipeline_5min_dlt_pipelines

Aciona a cada **5 minutos** os jobs Databricks de DLT em sequência:
1. `dm-trigger-dlt-ethereum` — atualiza o pipeline `dm-ethereum` (blockchain data)
2. `dm-trigger-dlt-app-logs` — atualiza o pipeline `dm-app-logs` (logs de aplicação)

O pipeline `dm-app-logs` depende da bronze `b_ethereum.kafka_topics_multiplexed`
gerada pelo `dm-ethereum`, portanto executa após ele.

### Por que este padrão?
O Databricks **Free Edition** não suporta pipelines DLT contínuos — o trigger
apenas executa como `availableNow` (processa os dados disponíveis e para).
Esta DAG substitui o trigger contínuo gerenciando a periodicidade externamente.

### Fluxo
```
Airflow (cada 5 min)
  ├── TRIGGER_DLT_ETHEREUM  (paralelo)
  │     └── pipeline_task → dm-ethereum (availableNow)
  │           ├── bronze: kafka_topics_multiplexed  (S3 → b_ethereum)
  │           └── silver: s_apps.*                  (Avro decode)
  └── TRIGGER_DLT_APP_LOGS  (paralelo)
        └── pipeline_task → dm-app-logs (availableNow)
              ├── silver: s_logs.logs_streaming, s_logs.logs_batch
              └── gold:   g_api_keys.etherscan_consumption, g_api_keys.web3_keys_consumption
```
""",
) as dag:

    TRIGGER_DLT_ETHEREUM = DatabricksRunNowOperator(
        task_id="TRIGGER_DLT_ETHEREUM",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}dm-trigger-dlt-ethereum",
        wait_for_termination=True,
        polling_period_seconds=30,
    )

    TRIGGER_DLT_APP_LOGS = DatabricksRunNowOperator(
        task_id="TRIGGER_DLT_APP_LOGS",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}dm-trigger-dlt-app-logs",
        wait_for_termination=True,
        polling_period_seconds=30,
    )

    # Tasks run in parallel — dm-app-logs reads from existing bronze (b_ethereum.*)
    # which is already persisted from previous runs. No sequential dependency needed.
    [TRIGGER_DLT_ETHEREUM, TRIGGER_DLT_APP_LOGS]
