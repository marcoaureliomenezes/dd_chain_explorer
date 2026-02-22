# Processamento Batch — Databricks Workflows

## Visão Geral

O processamento batch é organizado em três **Databricks Workflows** deployados via DABs:

| Workflow | Execução | Propósito |
|----------|----------|-----------|
| `dm-ddl-setup` | Manual (eventual) | Cria schemas e tabelas no Unity Catalog |
| `dm-periodic-processing` | A cada 6h | Identifica contratos populares e ingere histórico via Etherscan |
| `dm-iceberg-maintenance` | Diário às 2h (Horário de Brasília) | OPTIMIZE + VACUUM + monitoramento das tabelas Delta |
| `dm-teardown` | Manual (DEV only) | Remove toda a estrutura do catálogo |

Todos os workflows são definidos em `dabs/resources/workflows/` e os notebooks estão em `dabs/src/batch/`.

---

## Workflow 1 — DDL Setup (`dm-ddl-setup`)

**Arquivo:** `dabs/resources/workflows/workflow_ddl_setup.yml`  
**Execução:** manual (setup inicial do ambiente ou recriação de tabelas)

### Grafo de tarefas

```
create_bronze_tables
       ├──▶ create_silver_apps_tables
       │         └──▶ create_gold_views
       └──▶ create_silver_logs_table
                 └──▶ create_gold_views
```

### Tarefas

#### `create_bronze_tables` — `1_create_bronze_tables.py`

Cria o catálogo (se não existir), os schemas `b_fast` e `bronze`, e as tabelas Bronze:

| Tabela | Schema | Partição | Descrição |
|--------|--------|----------|-----------|
| `kafka_topics_multiplexed` | `b_fast` | `topic_name` | Landing zone de todos os tópicos Kafka |
| `popular_contracts_txs` | `bronze` | `ingestion_date` | Transações históricas de contratos populares |

Parâmetro: `catalog` (default: `dd_chain_explorer`)

---

#### `create_silver_apps_tables` — `2_create_silver_apps_tables.py`

Cria o schema `s_apps` e as tabelas Silver de dados de aplicação:

| Tabela | Partição | Delta CDF | Descrição |
|--------|----------|-----------|-----------|
| `mined_blocks_events` | — | ✅ | Eventos leves de blocos minerados |
| `blocks_fast` | — | ✅ | Dados completos de blocos |
| `transactions_fast` | `block_number` | ✅ | Transações completas |

---

#### `create_silver_logs_table` — `3_create_silver_logs_table.py`

Cria o schema `s_logs` e a tabela Silver de logs:

| Tabela | Partição | Descrição |
|--------|----------|-----------|
| `apps_logs_fast` | `job_name` | Logs de aplicação de todos os serviços Python |

---

#### `create_gold_views` — `4_create_gold_views.py`

Cria o schema `gold` e as views analíticas:

| View | Base | Descrição |
|------|------|-----------|
| `blocks_with_tx_count` | `s_apps.blocks_fast` | Blocos com contagem de transações e métricas de gas |
| `top_contracts_by_volume` | `s_apps.transactions_fast` | Contratos mais transacionados por hora (volume em Wei) |
| `blocks_hourly_summary` | `s_apps.blocks_fast` | Sumarização de blocos por hora |

---

### Como executar

```bash
# Via Makefile
make dabs_run_dev JOB=dm-ddl-setup

# Via CLI manualmente
cd dabs && databricks bundle run --target dev workflow_ddl_setup
```

---

## Workflow 2 — Periodic Processing (`dm-periodic-processing`)

**Arquivo:** `dabs/resources/workflows/workflow_periodic_processing.yml`  
**Schedule:** `0 0 */6 * * ?` — a cada 6 horas, fuso `America/Sao_Paulo`

### Grafo de tarefas

```
get_popular_contracts ──▶ ingest_contracts_txs
```

### Tarefas

#### `get_popular_contracts` — `1_get_popular_contracts.py`

**Objetivo:** Identificar os contratos Ethereum mais transacionados na janela atual.

**Mecanismo:**
1. Lê a tabela `s_apps.transactions_fast` (Silver) de um período recente.
2. Agrega por `to_address` (endereço do contrato) e conta transações.
3. Salva os top contratos na tabela DynamoDB `dm-popular-contracts`.

**Parâmetros:**
```
dynamodb_table: ${var.dynamodb_popular_contracts_table}
catalog:        ${var.catalog}
```

---

#### `ingest_contracts_txs` — `2_ingest_contracts_txs.py`

**Objetivo:** Para todos os contratos identificados no passo anterior, buscar o histórico completo de transações via Etherscan e persistir no lakehouse.

**Mecanismo:**
1. Lê os contratos populares da tabela DynamoDB `dm-popular-contracts`.
2. Para cada contrato, chama a API Etherscan (`etherScan/api?module=account&action=txlist`).
3. Salva transações brutas no S3 `dm-chain-explorer-raw-data/contracts_transactions/`.
4. Cria/atualiza a tabela `bronze.popular_contracts_txs` a partir dos arquivos S3.

**Parâmetros:**
```
raw_s3_bucket: ${var.raw_s3_bucket}
catalog:       ${var.catalog}
```

Configuração Spark adicional:
```
spark.hadoop.fs.s3a.aws.credentials.provider: InstanceProfileCredentialsProvider
```
(usa a IAM role do cluster Databricks para acessar o S3 sem credenciais estáticas)

---

### Como executar

```bash
make dabs_run_dev JOB=dm-periodic-processing
```

---

## Workflow 3 — Manutenção (`dm-iceberg-maintenance`)

**Arquivo:** `dabs/resources/workflows/workflow_maintenance.yml`  
**Schedule:** `0 0 2 * * ?` — diariamente às 2h, fuso `America/Sao_Paulo`

### Grafo de tarefas

```
optimize_bronze ──▶ optimize_silver
                          │
       ┌──────────────────┘
       ▼
optimize_bronze ──▶ vacuum_all ──▶ monitor_tables
```

Mais precisamente:

```
optimize_bronze ─────────────────────────────────┐
optimize_silver (depende de optimize_bronze) ────▶ vacuum_all ──▶ monitor_tables
```

### Tarefas

#### `optimize_bronze` — `1_optimize_bronze.py`

Executa `OPTIMIZE` com `ZORDER` em todas as tabelas do schema Bronze (`b_fast`, `bronze`).

Benefício: compacta arquivos pequenos gerados pelo streaming contínuo em arquivos maiores, melhorando a performance de leitura.

**Parâmetro:** `catalog`

---

#### `optimize_silver` — `2_optimize_silver.py`

Executa `OPTIMIZE` com `ZORDER` em todas as tabelas Silver (`s_apps`, `s_logs`).

**Parâmetro:** `catalog`

---

#### `vacuum_all` — `3_vacuum_all.py`

Executa `VACUUM` em todas as tabelas do catálogo para remover arquivos de versões antigas não referenciados.

**Parâmetros:**
```
catalog:          ${var.catalog}
retention_hours:  168    (7 dias — valor padrão Delta)
```

> Atenção: nunca abaixe `retention_hours` abaixo de `168` se o Time Travel for necessário.

---

#### `monitor_tables` — `4_monitor_tables.py`

Coleta e exibe métricas de saúde das tabelas:
- Row count total
- Tamanho em disco (MB)
- Número de arquivos
- Versão Delta atual

**Parâmetro:** `catalog`

A saída é exibida nos logs do job no Databricks.

---

### Como executar

```bash
make dabs_run_dev JOB=dm-iceberg-maintenance
```

---

## Workflow 4 — Teardown (`dm-teardown`)

**Arquivo:** `dabs/resources/workflows/workflow_teardown.yml`  
**Execução:** manual — **use apenas em DEV**

> ⚠️ **ATENÇÃO:** Este workflow apaga **todas** as tabelas, views e schemas do catálogo. A operação é irreversível.

### Tarefa única

#### `delete_all_tables` — `5_delete_all_tables.py`

Remove na seguinte ordem:
1. Views Gold (`gold.*`)
2. Tabelas Silver e Bronze (com `PURGE` por padrão)
3. Schemas (`b_fast`, `bronze`, `s_apps`, `s_logs`, `gold`)

**Parâmetros:**
```
catalog:  ${var.catalog}
purge:    "true"     (remove arquivos do storage imediatamente)
```

### Como executar

```bash
# Apenas em DEV — jamais em produção
make dabs_run_dev JOB=dm-teardown
```

---

## Configuração de Cluster (padrão todos os workflows)

Todos os jobs batch usam:

```yaml
spark_version: 15.4.x-scala2.12
node_type_id:  i3.xlarge
num_workers:   1   (exceto ingest_contracts_txs: 2)
```

---

## Notificações

Todos os workflows enviam e-mail em caso de falha:

```yaml
email_notifications:
  on_failure:
    - marco@example.com
```

Configure o e-mail correto no `databricks.yml` antes de fazer deploy em PROD.
