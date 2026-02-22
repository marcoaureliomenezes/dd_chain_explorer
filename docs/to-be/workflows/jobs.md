# Databricks Workflows (Jobs)

## Visão Geral

Os workflows batch são definidos em `dabs/resources/workflows/` e orquestram os notebooks em `dabs/src/batch/`. São deployados via DABs e visíveis no Databricks UI em **Workflows**.

---

## Workflows Deployados

| Workflow (nome em PROD) | Arquivo | Execução | Propósito |
|------------------------|---------|----------|-----------|
| `[prod] dm-ddl-setup` | `workflow_ddl_setup.yml` | Manual | Cria schemas, tabelas e views no Unity Catalog |
| `[prod] dm-periodic-processing` | `workflow_periodic_processing.yml` | A cada 6h | Identifica contratos populares + ingere histórico Etherscan |
| `[prod] dm-iceberg-maintenance` | `workflow_maintenance.yml` | Diário às 2h | OPTIMIZE + VACUUM + monitoramento |
| `[prod] dm-teardown` | `workflow_teardown.yml` | Manual (DEV only) | Remove toda a estrutura do catálogo |

---

## `dm-ddl-setup`

**Trigger:** manual  
**Grafo:**

```
create_bronze_tables
    ├── create_silver_apps_tables ──┐
    └── create_silver_logs_table ──┴── create_gold_views
```

| Task | Notebook | Resultado |
|------|----------|-----------|
| `create_bronze_tables` | `src/batch/ddl/1_create_bronze_tables.py` | Cria `b_fast.kafka_topics_multiplexed` e `bronze.popular_contracts_txs` |
| `create_silver_apps_tables` | `src/batch/ddl/2_create_silver_apps_tables.py` | Cria `s_apps.mined_blocks_events`, `s_apps.blocks_fast`, `s_apps.transactions_fast` |
| `create_silver_logs_table` | `src/batch/ddl/3_create_silver_logs_table.py` | Cria `s_logs.apps_logs_fast` |
| `create_gold_views` | `src/batch/ddl/4_create_gold_views.py` | Cria views Gold (`gold.blocks_with_tx_count`, `gold.top_contracts_by_volume`, `gold.blocks_hourly_summary`) |

**Parâmetro base:** `catalog = ${var.catalog}`

**Como executar:**
```bash
make dabs_run_dev JOB=dm-ddl-setup
# ou
cd dabs && databricks bundle run --target dev workflow_ddl_setup
```

---

## `dm-periodic-processing`

**Schedule:** `0 0 */6 * * ?` (todo dia a cada 6 horas) — `America/Sao_Paulo`  
**Grafo:**

```
get_popular_contracts ──▶ ingest_contracts_txs
```

| Task | Notebook | Resultado |
|------|----------|-----------|
| `get_popular_contracts` | `src/batch/periodic/1_get_popular_contracts.py` | Identifica contratos mais transacionados e salva em DynamoDB `dm-popular-contracts` |
| `ingest_contracts_txs` | `src/batch/periodic/2_ingest_contracts_txs.py` | Busca histórico de transações via Etherscan, salva em S3 e cria/atualiza `bronze.popular_contracts_txs` |

**Parâmetros:**
```
get_popular_contracts:
  dynamodb_table: ${var.dynamodb_popular_contracts_table}
  catalog:        ${var.catalog}

ingest_contracts_txs:
  raw_s3_bucket:  ${var.raw_s3_bucket}
  catalog:        ${var.catalog}
```

**Como executar:**
```bash
make dabs_run_dev JOB=dm-periodic-processing
```

---

## `dm-iceberg-maintenance`

**Schedule:** `0 0 2 * * ?` (diariamente às 2h) — `America/Sao_Paulo`  
**Grafo:**

```
optimize_bronze ──────────────────────────────────────┐
optimize_silver (após optimize_bronze) ───────────────┴──▶ vacuum_all ──▶ monitor_tables
```

| Task | Notebook | Parâmetros | O que faz |
|------|----------|-----------|-----------|
| `optimize_bronze` | `src/batch/maintenance/1_optimize_bronze.py` | `catalog` | `OPTIMIZE + ZORDER` em tabelas Bronze |
| `optimize_silver` | `src/batch/maintenance/2_optimize_silver.py` | `catalog` | `OPTIMIZE + ZORDER` em tabelas Silver |
| `vacuum_all` | `src/batch/maintenance/3_vacuum_all.py` | `catalog`, `retention_hours=168` | `VACUUM` em todas as tabelas (remove arquivos antigos) |
| `monitor_tables` | `src/batch/maintenance/4_monitor_tables.py` | `catalog` | Exibe métricas de row count, tamanho e versão Delta |

**Como executar:**
```bash
make dabs_run_dev JOB=dm-iceberg-maintenance
```

---

## `dm-teardown`

**Trigger:** manual | **Uso:** somente DEV  
**Grafo:** task única

| Task | Notebook | O que faz |
|------|----------|-----------|
| `delete_all_tables` | `src/batch/ddl/5_delete_all_tables.py` | Remove views Gold, tabelas Bronze/Silver (com PURGE), e todos os schemas |

**Parâmetros:**
```
catalog: ${var.catalog}
purge:   "true"
```

> ⚠️ **Irreversível.** Nunca execute em produção via CI/CD (tag `env: dev-only`).

**Como executar:**
```bash
make dabs_run_dev JOB=dm-teardown
```

---

## Referência Rápida dos Notebooks

```
dabs/src/batch/
├── ddl/
│   ├── 1_create_bronze_tables.py      ← cria b_fast + bronze
│   ├── 2_create_silver_apps_tables.py ← cria s_apps (blocks, txs)
│   ├── 3_create_silver_logs_table.py  ← cria s_logs
│   ├── 4_create_gold_views.py         ← cria gold views
│   └── 5_delete_all_tables.py         ← teardown (DEV)
├── maintenance/
│   ├── 1_optimize_bronze.py           ← OPTIMIZE Bronze
│   ├── 2_optimize_silver.py           ← OPTIMIZE Silver
│   ├── 3_vacuum_all.py                ← VACUUM geral
│   └── 4_monitor_tables.py            ← métricas das tabelas
└── periodic/
    ├── 1_get_popular_contracts.py     ← top contratos → DynamoDB
    └── 2_ingest_contracts_txs.py      ← Etherscan → S3 → Bronze
```

---

## Documentação Detalhada

Para descrição completa das tarefas, schemas e decisões técnicas, consulte [data_processing_batch.md](../application/data_processing_batch.md).
