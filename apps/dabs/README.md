# apps/dabs — Databricks Asset Bundles (DABs)

Recursos Databricks do projeto `dd-chain-explorer` gerenciados via [Databricks Asset Bundles](https://docs.databricks.com/en/dev-tools/bundles/index.html).

---

## Estrutura

```
apps/dabs/
  databricks.yml              # Bundle principal — targets, variáveis globais
  resources/
    dlt/
      pipeline_ethereum.yml   # DLT pipeline: streaming Ethereum (Kinesis → Bronze/Silver/Gold)
      pipeline_app_logs.yml   # DLT pipeline: logs de aplicação (CloudWatch → Bronze)
    workflows/
      workflow_ddl_setup.yml        # DDL inicial (Bronze + Silver + Gold views + RLS)
      workflow_dlt_full_refresh.yml # Full refresh manual dos 2 pipelines DLT
      workflow_maintenance.yml      # OPTIMIZE + VACUUM (schedule 12h)
      workflow_batch_contracts.yml  # S3 batch/ → Bronze → Silver (contratos)
    dashboards/               # 4 Lakeview dashboards
    alerts/                   # Alertas de API keys e DynamoDB deadlock
    genie/                    # Genie AI/BI space
  src/
    streaming/
      4_pipeline_ethereum.py  # DLT streaming: Kinesis → tabelas Ethereum
      5_pipeline_app_logs.py  # DLT streaming: CloudWatch Logs → tabelas de logs
    batch/
      ddl/                    # Scripts de criação de tabelas e views
      batch_contracts/        # S3 → Bronze → Silver para contratos
      maintenance/            # OPTIMIZE, VACUUM, monitoramento
```

---

## Targets

| Target | Workspace | Catalog | Modo DLT |
|--------|-----------|---------|----------|
| `dev` | Databricks Free Edition | `dev` | triggered (availableNow) |
| `hml` | Databricks Free Edition | `hml` | triggered — deploy only via CI/CD |
| `prod` | Databricks AWS workspace | `dd_chain_explorer` | triggered |

---

## Workflows

### `dm-ddl-setup`
Cria todas as tabelas Bronze, Silver e views Gold no Unity Catalog. Deve ser executado uma vez antes do primeiro deploy dos pipelines DLT.

**Tasks**: `create_bronze_tables` → `create_silver_apps_tables` + `create_silver_logs_table` → `create_gold_views` → `create_rls_policies`

---

### `dm-dlt-full-refresh`
Reprocessa todos os dados desde a fonte descartando checkpoints DLT. Uso: reprocessamento histórico ou após schema evolution.

**Tasks**: `full_refresh_ethereum` → `full_refresh_app_logs`

---

### `dm-iceberg-maintenance`
OPTIMIZE + VACUUM em todas as tabelas Delta. Schedule: 2x por dia (4h e 16h).

**Tasks**: `optimize_bronze` → `optimize_silver` → `vacuum_all` → `monitor_tables`

---

### `dm-batch-contracts`
Ingesta transações de contratos do S3 (`batch/` prefix) para Bronze e processa até Silver.

**Tasks**: `s3_to_bronze_contracts_txs` → `bronze_to_silver_contracts_txs`

---

## Pipelines DLT

### `dm-ethereum`
Consome dados do Kinesis Firehose (arquivos Parquet no S3) e popula as tabelas:
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

# Ver status dos recursos
make dabs_status_dev
```

### PROD (CI/CD)

Deploy via `.github/workflows/deploy_dm_applications.yml` (app_type=databricks-dabs):

```
dabs-check-infra → dabs-check-version → dabs-validate
→ dabs-deploy-hml → dabs-hml-integration-test → dabs-deploy-prod
```

### Deploy manual PROD

```bash
cd apps/dabs
databricks bundle deploy --target prod
```

---

## Variáveis

| Variável | DEV | PROD |
|----------|-----|------|
| `catalog` | `dev` | `dd_chain_explorer` |
| `ingestion_s3_bucket` | `dm-chain-explorer-dev-ingestion` | `dm-chain-explorer-prd-ingestion` |
| `dynamodb_table` | `dm-chain-explorer` | `dm-chain-explorer` |
| `dlt_development` | `true` | `false` |
| `dlt_continuous` | `false` | `false` |
| `warehouse_id` | auto-descoberto via CLI | — |
