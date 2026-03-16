import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.models.param import Param
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from python_scripts.alerts import slack_alert


default_args = {
    "owner": "airflow",
    "email_on_failure": True,
    "email_on_retry": False,
    "email": "marco_aurelio_reis@yahoo.com.br",
    "retries": 0,  # sem retry automático — backfill deve ser reiniciado manualmente
    "on_failure_callback": slack_alert,
}

# Prefixo injetado pelo Airflow via compose (ex: "[dev marcoaurelioreislima] ")
JOB_PREFIX = os.getenv("DATABRICKS_JOB_NAME_PREFIX", "")

with DAG(
    "pipeline_backfill_reprocess",
    start_date=datetime(year=2026, month=1, day=1),
    schedule_interval=None,   # somente trigger manual via UI / CLI / API
    default_args=default_args,
    max_active_runs=1,        # impede runs concorrentes que corrompem checkpoints
    catchup=False,
    params={
        "pipeline": Param(
            default="both",
            enum=["ethereum", "app_logs", "both"],
            description=(
                "Qual pipeline DLT reprocessar.\n"
                "  'ethereum'  — apenas dm-ethereum (blockchain data)\n"
                "  'app_logs'  — apenas dm-app-logs (application logs)\n"
                "  'both'      — Ethereum primeiro, depois app-logs em sequência"
            ),
        ),
        "reason": Param(
            default="",
            type="string",
            description="Motivo do reprocessamento (registrado no log e alerta Slack).",
        ),
    },
    tags=["databricks", "dlt", "backfill", "manual"],
    doc_md="""
## pipeline_backfill_reprocess

DAG de **reprocessamento manual** dos pipelines DLT.

Deve ser disparada manualmente pela UI do Airflow (botão *Trigger DAG*) quando
for necessário reprocessar dados históricos, por exemplo após:
- Correção de lógica de transformação (Silver/Gold)
- Reingestion após retenção de dados ultrapassada
- Correção de schemas ou expectativas DLT

### Parâmetros

| Parâmetro  | Valores               | Descrição                                      |
|------------|-----------------------|------------------------------------------------|
| `pipeline` | `ethereum`, `app_logs`, `both` | Qual pipeline reprocessar        |
| `reason`   | texto livre           | Motivo do reprocessamento (auditoria)          |

### O que acontece internamente?

1. Aciona o job `dm-dlt-full-refresh` no Databricks com `full_refresh=true`
2. O job para o pipeline DLT selecionado, descarta checkpoints e reprocessa
   todos os dados disponíveis na fonte (S3 DEV / Kafka PROD)
3. Em DEV: reprocessa todos os arquivos presentes no bucket `dm-chain-explorer-dev-ingestion`
4. Em PROD: reprocessa desde o Kafka (limitado pela retenção configurada no MSK)

### Atenção

- Em PROD, o pipeline contínuo será interrompido durante o full_refresh e
  reconectado automaticamente ao fim. Haverá janela de indisponibilidade.
- Para reprocessar apenas uma tabela DLT, use a Databricks UI diretamente
  (Pipeline → `...` → *Full refresh selection*).
""",
) as dag:

    RUN_FULL_REFRESH = DatabricksRunNowOperator(
        task_id="RUN_FULL_REFRESH",
        databricks_conn_id="databricks_default",
        job_name=f"{JOB_PREFIX}dm-dlt-full-refresh",
        wait_for_termination=True,
        polling_period_seconds=60,
    )

    RUN_FULL_REFRESH
