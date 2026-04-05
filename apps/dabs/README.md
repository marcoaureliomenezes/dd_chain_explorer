# apps/dabs — Databricks Asset Bundles (DABs)

Recursos Databricks do projeto `dd-chain-explorer` gerenciados via [Databricks Asset Bundles](https://docs.databricks.com/en/dev-tools/bundles/index.html).

---

## Estrutura

```
apps/dabs/
  databricks.yml              # Bundle principal — targets, variáveis globais
  resources/
    dlt/
      pipeline_ethereum.yml   # DLT pipeline: streaming Ethereum (S3 → Bronze/Silver/Gold)
      pipeline_app_logs.yml   # DLT pipeline: logs de aplicação (CloudWatch → Bronze)
    workflows/
      workflow_ddl_setup.yml             # DDL inicial (Bronze + Silver + Gold views)
      workflow_dlt_full_refresh.yml      # Full refresh manual dos 2 pipelines DLT + export Gold
      workflow_maintenance.yml           # OPTIMIZE + VACUUM (schedule 12h)
      workflow_batch_contracts.yml       # S3 batch/ → Bronze → Silver (contratos)
      workflow_trigger_dlt_all.yml       # Disparo sequencial ethereum → app_logs (schedule 1h — UNPAUSED em DEV)
      workflow_trigger_dlt_ethereum.yml  # CI trigger: dispara pipeline ethereum uma vez
      workflow_trigger_dlt_app_logs.yml  # CI trigger: dispara pipeline app_logs uma vez
    dashboards/               # 4 Lakeview dashboards
    alerts/                   # Alertas de API keys e DynamoDB deadlock
    genie/                    # Genie AI/BI space
  src/
    streaming/
      4_pipeline_ethereum.py  # DLT streaming: S3 NDJSON → tabelas Ethereum
      5_pipeline_app_logs.py  # DLT streaming: CloudWatch Logs → tabelas de logs
    batch/
      ddl/setup_ddl.py           # DDL unificado (Spark + Warehouse dual-mode)
      maintenance/maintenance.py # OPTIMIZE, VACUUM, monitoramento (consolidado)
      periodic/4_export_gold_to_s3.py  # Exporta tabelas Gold para S3
    dd_chain_explorer/         # Pacote Python (wheel) para python_wheel_task
      batch_contracts/         # entry points: dd-s3-to-bronze, dd-bronze-to-silver
    pyproject.toml             # Definição do wheel dd_chain_explorer
```

---

## Targets

| Target | Workspace | Catalog | Modo DLT |
|--------|-----------|---------|----------|
| `dev` | Databricks Free Edition | `dev` | triggered (availableNow) |
| `hml` | Databricks Free Edition | `hml` | triggered — deploy only via CI/CD |
| `prod` | Databricks AWS workspace | `dd_chain_explorer` | triggered, `run_as: marcoaurelioreislima@gmail.com` |

---

## Workflows

### `dm-ddl-setup`
Cria todos os schemas, tabelas Bronze, Silver e views Gold no Unity Catalog via um único script consolidado `setup_ddl.py`.

**Task**: `setup_ddl` — `spark_python_task` em `apps/dabs/src/batch/ddl/setup_ddl.py`

**Modo dual de execução:**
- **HML/PROD** (com cluster Spark): `spark.sql()`
- **DEV (Free Edition)**: Databricks Statements REST API (sem Spark cluster) — use `make dabs_ddl_dev`

**Tasks**: `setup_ddl` (task única substituindo os 5 notebooks anteriores)

---

### `dm-dlt-full-refresh`
Reprocessa todos os dados desde a fonte descartando checkpoints DLT. Uso: reprocessamento histórico ou após schema evolution. Ao final, exporta tabelas Gold para S3.

**Tasks**: `full_refresh_ethereum` → `full_refresh_app_logs` → `export_gold_to_s3`

---

### `dm-iceberg-maintenance`
OPTIMIZE + VACUUM em todas as tabelas Delta. Schedule: 2x por dia (4h e 16h).

**Tasks**: `optimize_bronze` → `optimize_silver` → `vacuum_all` → `monitor_tables`

---

### `dm-batch-contracts`
Ingesta transações de contratos do S3 (`batch/` prefix) para Bronze e processa até Silver.

**Tasks**: `s3_to_bronze_contracts_txs` → `bronze_to_silver_contracts_txs`

### `dm-trigger-all-dlts`
Dispara sequencialmente os pipelines `dm-ethereum` → `dm-app-logs` a cada 1 hora. Em DEV o schedule é ativo (`UNPAUSED`); em HML e PROD é pausado (disparado via CI ou manualmente).

### `dm-trigger-dlt-ethereum`
Workflow CI — dispara o pipeline `dm-ethereum` uma vez e aguarda conclusão (`full_refresh: false`). Sem schedule.

### `dm-trigger-dlt-app-logs`
Workflow CI — dispara o pipeline `dm-app-logs` uma vez e aguarda conclusão (`full_refresh: false`). Sem schedule.

---

## Pipelines DLT

### `dm-ethereum`
Consome NDJSON do S3 via Auto Loader (entregues pelo Firehose: Kinesis-source para transactions-data; Direct Put para blocks-data e decoded-txs) e popula as tabelas:
- Bronze: `b_ethereum.*` (mined blocks, block data, transactions, decoded inputs)
- Silver: `s_apps.*` (dados limpos e normalizados)
- Gold: views materializadas para consumo externo

**Schedule**: configurado diretamente no pipeline (`pipeline_ethereum.yml`).

### `dm-app-logs`
Consome logs de aplicação do CloudWatch Logs (via Firehose → S3) e popula:
- Bronze: `b_ethereum.app_logs`
- Silver: `s_logs.*`

**Schedule**: configurado diretamente no pipeline (`pipeline_app_logs.yml`).

---

## Deploy

### DEV (local)

```bash
# Deploy completo
make dabs_deploy_dev

# Deploy com dashboard auto-descoberta de warehouse
make dabs_deploy_dev_dashboards

# Executar um workflow em DEV
make dabs_run_dev JOB=dm-ddl-setup
make dabs_run_dev JOB=dm-batch-contracts
make dabs_run_dev JOB=dm-iceberg-maintenance

# Executar pipelines DLT em sequência (ethereum → app_logs)
make run_dev_pipelines

# Setup DDL no DEV via SQL Warehouse (sem Spark cluster)
make dabs_ddl_dev             # cria/atualiza schemas e tabelas
make dabs_ddl_dev DROP=1      # DROP CASCADE + recria tudo
make dabs_ddl_dev COMMENTS=1  # aplica somente comentários

# Pausar schedule do dm-trigger-all-dlts antes de deploy HML
make pause_dlt_pipelines

# Ver status dos recursos
make dabs_status_dev
```

### PROD (CI/CD)

Deploy via `.github/workflows/deploy_all_dm_applications.yml` (DABs):

```
all-stream-build-rc + dabs-validate + lambda-build (paralelo)
→ hml-provision → hml-deploy-ecs → hml-deploy-dabs → hml-test
→ hml-teardown → check-prd-infra → prd-deploy-streaming → prd-deploy-dabs → prd-create-tags
```

### Deploy manual PROD

```bash
cd apps/dabs
databricks bundle deploy --target prod
```

---

## Variáveis

| Variável | DEV | HML | PROD |
|----------|-----|------|
| `catalog` | `dev` | `hml` | `dd_chain_explorer` |
| `ingestion_s3_bucket` | `dm-chain-explorer-dev-ingestion` | `dm-chain-explorer-hml-lakehouse` | `dm-chain-explorer-lakehouse` |
| `dynamodb_table` | `dm-chain-explorer` | `dm-chain-explorer-hml` | `dm-chain-explorer` |
| `dlt_development` | `true` | `false` | `false` |
| `dlt_continuous` | `false` | `false` | `false` |
| `warehouse_id` | auto-descoberto via CLI | — | — |
