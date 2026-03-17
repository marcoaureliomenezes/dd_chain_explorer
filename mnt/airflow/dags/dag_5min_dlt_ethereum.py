import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from python_scripts.alerts import slack_alert


default_args = {
    "owner": "airflow",
    "email_on_failure": True,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "on_failure_callback": slack_alert,
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

Aciona a cada **5 minutos** os jobs Databricks de DLT **em sequência**:
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
  1. TRIGGER_DLT_ETHEREUM  (sequencial — roda primeiro)
       └── pipeline_task → dm-ethereum (availableNow)
             ├── bronze: kafka_topics_multiplexed  (S3 → b_ethereum)
             └── silver: s_apps.*                  (Avro decode)
  2. TRIGGER_DLT_APP_LOGS  (sequencial — roda após ethereum)
       └── pipeline_task → dm-app-logs (availableNow)
             ├── silver: s_logs.logs_streaming, s_logs.logs_batch
             └── gold:   g_api_keys.etherscan_consumption, g_api_keys.web3_keys_consumption
```

### Por que sequencial?
O Databricks **Free Edition** permite apenas **1 pipeline DLT ativo** por vez
(QUOTA_EXCEEDED_EXCEPTION: Limit: 1). Rodar em paralelo causa falha no segundo.
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

    # Sequential: Free Edition allows only 1 active DLT pipeline at a time.
    # dm-ethereum must complete before dm-app-logs starts (also a data dependency:
    # dm-app-logs reads from b_ethereum.kafka_topics_multiplexed).
    TRIGGER_DLT_ETHEREUM >> TRIGGER_DLT_APP_LOGS
