# 03 — Processamento de Dados

## Visão Geral

O processamento analítico é implementado no **Databricks** com **Delta Live Tables (DLT)** seguindo a arquitetura medalhão (Bronze → Silver → Gold). Dois pipelines DLT processam os dados, complementados por workflows batch para ingestão de contratos, setup/teardown e manutenção.

A orquestração é feita nativamente pelo **Databricks Workflows** (schedules Quartz cron) e **AWS Lambda + EventBridge** para ingestão batch de contratos.

---

## 1. Pipelines DLT

### 1.1 Pipeline `dm-ethereum` (Principal)

Pipeline unificado Bronze + Silver + Gold definido em `4_pipeline_ethereum.py`. Contém a lógica completa de transformação dos dados on-chain.

**Configuração:**

| Parâmetro | DEV | PROD |
|-----------|-----|------|
| `source.type` | `s3` (Auto Loader sobre NDJSON) | `s3` (Auto Loader sobre NDJSON via Firehose) |
| `dlt_continuous` | `false` (triggered por Workflow `dm-trigger-dlt-all` a cada 5 min) | `false` (triggered por Workflow schedule) |
| `dlt_development` | `true` | `false` |
| `serverless` | `true` | `true` |
| Catalog | `dev` | `dd_chain_explorer` |

#### Bronze — `b_ethereum.kafka_topics_multiplexed`

Tabela única multiplexada com todos os tópicos Kafka, particionada por `topic_name`.

**Dual-source:**
- **DEV**: Lê Parquet do S3 via Auto Loader (`cloudFiles`). Dados previamente escritos pelo job Spark `kafka_to_s3_multiplex`.
- **PROD**: Lê diretamente do Kafka MSK com autenticação IAM (`SASL_SSL` + `AWS_MSK_IAM`).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `topic_name` | string | Nome do tópico Kafka (coluna de partição) |
| `kafka_partition` | int | Partição Kafka original |
| `kafka_offset` | long | Offset Kafka |
| `kafka_timestamp` | timestamp | Timestamp do Kafka |
| `key` | string | Chave da mensagem (cast para string) |
| `value` | binary | Payload Avro com header Confluent (5 bytes) |

#### Silver — Tabelas Individuais

A camada Silver deserializa o payload Avro, remove o header Confluent (5 bytes: `substring(value, 6)`), aplica validações (`expect_or_drop`) e produz tabelas limpas.

**Tabelas no schema `s_apps`:**

| Tabela | Tópico Kafka Fonte | Campos Principais | Validações |
|--------|-------------------|-------------------|------------|
| `mined_blocks_events` | `mainnet.1.mined_blocks.events` | `block_number`, `block_hash`, `block_timestamp`, `event_time` | `block_number IS NOT NULL`, `block_hash IS NOT NULL` |
| `blocks_fast` | `mainnet.2.blocks.data` | `block_number`, `block_hash`, `parent_hash`, `block_time`, `miner`, `gas_limit`, `gas_used`, `base_fee_per_gas`, `transaction_count`, `transactions[]`, `withdrawals[]` | `block_number IS NOT NULL`, `block_hash IS NOT NULL` |
| `transaction_hash_ids` | `mainnet.3.block.txs.hash_id` | `tx_hash`, `block_hash` | `tx_hash IS NOT NULL` |
| `transactions_fast` | `mainnet.4.transactions.data` | `tx_hash`, `block_number`, `block_hash`, `from_address`, `to_address`, `value`, `input`, `gas`, `gas_price`, `tx_type`, `access_list[]`, **`event_date`** | `tx_hash IS NOT NULL`, `block_number IS NOT NULL`, **`valid_from_address`** (`^0x[a-fA-F0-9]{40}$`), **`valid_to_address`** (null ou `^0x[a-fA-F0-9]{40}$`) |
| `txs_inputs_decoded_fast` | `mainnet.5.transactions.input_decoded` | `tx_hash`, `contract_address`, `method`, `parms`, `decode_type` | `tx_hash IS NOT NULL` |
| `transactions_ethereum` | JOIN: `transactions_fast` + `txs_inputs_decoded_fast` + `blocks_fast` | Todos campos da tx + `tx_timestamp`, `block_gas_limit`, `block_gas_used`, `base_fee_per_gas`, `contract_address`, `method`, `parms`, `decode_type`, `input_etherscan`, **`event_date`** | `tx_hash IS NOT NULL`, `block_number IS NOT NULL`, **`valid_from_address`**, **`valid_to_address`** |
| `blocks_withdrawals` | Explode `blocks_fast.withdrawals[]` | `block_number`, `block_timestamp`, `miner`, `withdrawal_index`, `validator_index`, `withdrawal_address`, `amount_gwei`, `amount_eth` | — |

> **Particionamento:** `transactions_fast` e `transactions_ethereum` são particionadas por `event_date = to_date(kafka_timestamp)`, reduzindo o scan de queries por janela temporal.

**Tabela `transactions_ethereum`** — Detalhamento do JOIN:

```mermaid
flowchart LR
    TXS["transactions_fast<br/>(streaming)"]
    DEC["txs_inputs_decoded_fast<br/>(batch read)"]
    BLK["blocks_fast<br/>(batch read)"]
    OUT["transactions_ethereum<br/>(streaming output)"]

    TXS -->|"LEFT JOIN ON tx_hash"| J1["join 1"]
    DEC --> J1
    J1 -->|"LEFT JOIN ON block_number"| J2["join 2"]
    BLK --> J2
    J2 --> OUT
```

O join é implementado como stream-static: `transactions_fast` é lido via `dlt.read_stream()`, enquanto `txs_inputs_decoded_fast` e `blocks_fast` são lidos via `dlt.read()` (snapshot estático).

**Tabela `blocks_withdrawals`** — Explode os dados de saques ETH da Beacon Chain (EIP-4895). Cada withdrawal do bloco gera uma linha com `amount_gwei` e `amount_eth` (÷1e9).

#### Gold — Materialized Views

Quatro materialized views no schema `s_apps`:

| MV / Tabela | Descrição | Lógica |
|-------------|-----------|--------|
| `popular_contracts_ranking` | Top 100 contratos por volume de txs na última hora | Agrupa por `to_address` de `transactions_fast`, conta txs, endereços únicos (`unique_senders`), filtra última 1h |
| `peer_to_peer_txs` | Transferências ETH diretas (EOA→EOA) | Filtra `transactions_ethereum` onde `input` é nulo/vazio/`"0x"` (sem chamada de contrato) |
| `ethereum_gas_consume` | Consumo de gas por transação | Classifica transações em: `contract_deploy` (to=null, input≠vazio), `peer_to_peer` (input vazio), `contract_interaction` (demais). Calcula `gas_pct_of_block`. |
| `transactions_lambda` | Visão Lambda unificando streaming + batch | Faz UNION de `transactions_ethereum` (streaming) com `popular_contracts_txs` (batch), deduplica por `tx_hash` com prioridade por `decode_type`: `full (1) > full_4byte (2) > partial (3) > batch_sem_decode (4) > unknown (5)`. |
| `g_network.network_metrics_hourly` | Métricas de rede Ethereum agregadas por hora | JOIN `blocks_fast` + `transactions_fast`, agrupa por `hour_bucket = date_trunc('hour', kafka_timestamp)`. Calcula: `block_count`, `tx_count`, `tps_avg` (tx_count/3600), `avg_gas_price_gwei`, `avg_block_gas_used`, `avg_block_gas_limit`, `avg_block_utilization_pct`, `avg_txs_per_block`. |

### 1.2 Pipeline `dm-app-logs`

Pipeline dedicado ao processamento de logs das aplicações, definido em `5_pipeline_app_logs.py`.

**Configuração:**
- Catalog: variável (`dev` ou `dd_chain_explorer`)
- Lê da bronze `b_ethereum.kafka_topics_multiplexed` (produzida pelo pipeline `dm-ethereum`)
- Target schema: `s_logs`

#### Silver — `s_logs`

| Tabela | Filtro | Descrição |
|--------|--------|-----------|
| `logs_streaming` | `logger IN ('MINED_BLOCKS_EVENTS', 'ORPHAN_BLOCKS_CRAWLER', 'BLOCK_DATA_CRAWLER', 'RAW_TXS_CRAWLER', 'TRANSACTION_INPUT_DECODER')` | Logs dos 5 jobs de streaming |
| `logs_batch` | `logger IN ('CONTRACT_TRANSACTIONS_CRAWLER')` | Logs dos jobs batch |

#### Gold — `g_api_keys`

| MV | Descrição | Lógica |
|----|-----------|--------|
| `etherscan_consumption` | Consumo de API keys Etherscan | Filtra mensagens com `etherscan;api_call;`, extrai `api_key_name`, `action`, `status` via regex. Agrega por key com janelas de 1h/2h/12h/24h/48h. |
| `web3_keys_consumption` | Consumo de API keys Web3 (Infura/Alchemy) | Filtra `API_request;`, extrai key name e vendor. Classifica status (ok/error/http_error). Agrega por key+vendor com mesmas janelas. |

---

## 2. Modelo de Dados

### 2.1 Catalogs e Schemas

```
Unity Catalog
├── dev (DEV) / dd_chain_explorer (PROD)
│   ├── b_ethereum              ← Bronze
│   │   ├── kafka_topics_multiplexed (streaming table)
│   │   └── popular_contracts_txs    (batch table — S3)
│   │
│   ├── s_apps                  ← Silver (apps)
│   │   ├── mined_blocks_events      (streaming table)
│   │   ├── blocks_fast               (streaming table)
│   │   ├── transaction_hash_ids      (streaming table)
│   │   ├── transactions_fast         (streaming table — partitioned by event_date)
│   │   ├── txs_inputs_decoded_fast   (streaming table)
│   │   ├── transactions_ethereum     (streaming table — enriched, partitioned by event_date)
│   │   ├── blocks_withdrawals        (streaming table)
│   │   ├── popular_contracts_ranking (materialized view)
│   │   ├── peer_to_peer_txs          (materialized view)
│   │   ├── ethereum_gas_consume      (materialized view)
│   │   └── transactions_lambda       (materialized view)
│   │
│   ├── s_logs                  ← Silver (logs)
│   │   ├── logs_streaming            (streaming table)
│   │   └── logs_batch                (streaming table)
│   │
│   ├── g_api_keys              ← Gold (API keys)
│   │   ├── etherscan_consumption     (materialized view)
│   │   └── web3_keys_consumption     (materialized view)
│   │
│   ├── g_network               ← Gold (métricas de rede)
│   │   └── network_metrics_hourly    (materialized view)
│   │
│   └── g_contracts             ← Gold (contratos)
│       └── popular_contracts_history (Delta — SCD Type 2)
```

### 2.2 Diagrama de Linhagem

```mermaid
flowchart TB
    subgraph BRONZE["Bronze — b_ethereum"]
        B1["kafka_topics_multiplexed<br/>(partitioned by topic_name)"]
        B2["popular_contracts_txs<br/>(batch, S3)"]
    end

    subgraph SILVER_APPS["Silver — s_apps"]
        S1["mined_blocks_events"]
        S2["blocks_fast"]
        S3["transaction_hash_ids"]
        S4["transactions_fast"]
        S5["txs_inputs_decoded_fast"]
        S6["transactions_ethereum<br/>(enriched JOIN)"]
        S7["blocks_withdrawals<br/>(exploded)"]
    end

    subgraph GOLD_APPS["Gold — s_apps (MVs)"]
        G1["popular_contracts_ranking"]
        G2["peer_to_peer_txs"]
        G3["ethereum_gas_consume"]
        G4["transactions_lambda"]
    end

    subgraph SILVER_LOGS["Silver — s_logs"]
        SL1["logs_streaming"]
        SL2["logs_batch"]
    end

    subgraph GOLD_KEYS["Gold — g_api_keys (MVs)"]
        GK1["etherscan_consumption"]
        GK2["web3_keys_consumption"]
    end

    B1 --> S1
    B1 --> S2_
    B1 --> S3
    B1 --> S4
    B1 --> S5
    B1 --> SL1
    B1 --> SL2

    S2["blocks_fast"] --> S6
    S4 --> S6
    S5 --> S6
    S2 --> S7

    S4 --> G1
    S6 --> G2
    S6 --> G3
    S6 --> G4
    B2 --> G4

    SL1 --> GK1
    SL2 --> GK1
    SL1 --> GK2
    SL2 --> GK2
```

---

## 3. Workflows Batch (Databricks)

Definidos como Databricks Workflows via DABs (`dabs/resources/workflows/`):

### 3.1 DDL Setup (`dm-ddl-setup`)

Cria todas as tabelas e views no Unity Catalog. Executado uma vez na preparação do ambiente.

```
create_bronze_tables
    ├── create_silver_apps_tables
    └── create_silver_logs_table
          └── create_gold_views
```

### 3.2 Teardown (`dm-teardown`)

Deleta todas as tabelas e schemas. Apenas para ambiente DEV. Parâmetro `purge: "true"`.

### 3.3 Batch S3 → Bronze (`dm-batch-s3-to-bronze`)

Carrega dados JSON de contratos do S3 para a tabela bronze `popular_contracts_txs`.

### 3.4 Batch Bronze → Silver (`dm-batch-bronze-to-silver`)

Transforma dados de contratos da bronze para silver.

### 3.5 Manutenção (`dm-iceberg-maintenance`)

Executado a cada 12 horas:
```
optimize_bronze → optimize_silver → vacuum_all → monitor_tables
```
- **OPTIMIZE**: Compacta arquivos pequenos em Delta Lake
- **VACUUM**: Remove arquivos antigos não referenciados (após retention period)
- **Monitor**: Coleta métricas das tabelas

### 3.6 Processamento Periódico (`dm-periodic-processing`)

Executado a cada 6 horas via cron (`0 0 */6 * * ?`):
```
get_popular_contracts → ingest_contracts_txs
                     ↘ popular_contracts_scd2
```
1. Consulta contratos populares e salva no DynamoDB
2. `ingest_contracts_txs`: ingere transações desses contratos via Etherscan ao S3
3. `popular_contracts_scd2`: aplica SCD Type 2 em `g_contracts.popular_contracts_history` (tarefas 2 e 3 executam em paralelo, ambas dependem de `get_popular_contracts`)

### 3.7 Full Refresh DLT (`dm-dlt-full-refresh`)

Acionado manualmente via DAG `pipeline_backfill_reprocess`. Executa ambos os pipelines DLT com `full_refresh: true`, descartando checkpoints e reprocessando todos os dados disponíveis na fonte:
```
full_refresh_ethereum → full_refresh_app_logs
```

### 3.8 Trigger DLT (`dm-trigger-dlt-ethereum` / `dm-trigger-dlt-app-logs`)

Jobs individuais que disparam `pipeline_task` nos pipelines DLT com `full_refresh: false`. **PAUSADOS** — substituídos pelo workflow consolidado `dm-trigger-dlt-all` que dispara ambos sequencialmente.

---

## 4. Orquestração (Databricks Workflows + Lambda)

### 4.1 Workflows Agendados

| Workflow | Schedule | Descrição |
|----------|----------|----------|
| `dm-trigger-dlt-all` | A cada 5 min | Dispara pipelines DLT Ethereum → App Logs sequencialmente |
| `dm-periodic-processing` | A cada 1h | get_popular_contracts → ingest_contracts_txs → S3→Bronze → Bronze→Silver → SCD2 |
| `dm-iceberg-maintenance` | A cada 12h (4 AM/PM) | OPTIMIZE + VACUUM nas tabelas Delta |

### 4.2 Lambda + EventBridge

| Recurso | Schedule | Descrição |
|---------|----------|----------|
| Lambda `contracts-ingestion` | A cada 1h (EventBridge) | Etherscan API → JSON → S3 `batch/` |

### 4.3 Workflows Manuais

| Workflow | Descrição |
|----------|----------|
| `dm-ddl-setup` | Criação de tabelas Databricks |
| `dm-teardown` | Remoção de tabelas |
| `dm-dlt-full-refresh` | Reprocessamento completo DLT (full_refresh) |
| `dm-batch-s3-to-bronze` | Carga manual S3 → Bronze |
| `dm-batch-bronze-to-silver` | Carga manual Bronze → Silver |

### 4.4 Scripts de Limpeza (standalone)

| Script | Descrição |
|--------|----------|
| `scripts/environment/cleanup_s3.py` | Deleta objetos S3 por prefixo |
| `scripts/environment/cleanup_dynamodb.py` | Deleta todos itens de uma tabela DynamoDB |

```mermaid
flowchart LR
    EB["EventBridge<br/>(cada 1h)"] --> LAMBDA["Lambda<br/>contracts-ingestion"]
    LAMBDA --> S3["S3 batch/"]
    DW["Databricks Workflow<br/>(cada 5 min)"] --> DLT["DLT Ethereum + App Logs"]
    DW2["Databricks Workflow<br/>(cada 1h)"] --> PROC["S3 → Bronze → Silver → Gold"]
```

---

## 5. Deserialização Avro no DLT

Os dados na camada Bronze são armazenados como binário (`value` column) no formato **Confluent Wire Format**:

```
Byte 0:      Magic byte (0x00)
Bytes 1-4:   Schema ID (int32 big-endian)
Bytes 5+:    Payload Avro binário
```

Para deserializar no Spark:
```python
df.withColumn("avro_payload", F.expr("substring(value, 6)"))
  .withColumn("parsed", from_avro(F.col("avro_payload"), avro_schema_json))
```

Os schemas Avro são definidos centralizados no notebook `avro_schemas.py` e carregados nos pipelines DLT via `%run ./avro_schemas`. Isso elimina duplicação entre `4_pipeline_ethereum.py` e `5_pipeline_app_logs.py` e facilita manutenção.

Os 6 schemas disponíveis são: `AVRO_SCHEMA_APP_LOGS`, `AVRO_SCHEMA_MINED_BLOCKS_EVENTS`, `AVRO_SCHEMA_BLOCKS`, `AVRO_SCHEMA_TX_HASH_IDS`, `AVRO_SCHEMA_TRANSACTIONS`, `AVRO_SCHEMA_INPUT_DECODED`.

---

## 6. Diferenças DEV vs PROD no Processamento

| Aspecto | DEV | PROD |
|---------|-----|------|
| **Fonte Bronze** | S3 NDJSON via Auto Loader (`cloudFiles`) | S3 NDJSON via Auto Loader (Firehose) |
| **DLT Mode** | Triggered (Workflow a cada 5 min, `availableNow`) | Triggered (Workflow schedule) |
| **Development Flag** | `true` (permite refresh rápido) | `false` |
| **Workers** | 0 (single-node) | 1+ |
| **Catalog** | `dev` | `dd_chain_explorer` |
| **Batch Ingestion** | Manual / scripts | Lambda + EventBridge (hourly) |

---

## Referências de Arquivos

| Escopo | Arquivos |
|--------|----------|
| Schemas Avro centralizados | `dabs/src/streaming/avro_schemas.py` |
| Pipeline Ethereum (Bronze+Silver+Gold) | `dabs/src/streaming/4_pipeline_ethereum.py` |
| Pipeline App Logs (Silver+Gold) | `dabs/src/streaming/5_pipeline_app_logs.py` |
| Pipeline Bronze Multiplex (standalone) | `dabs/src/streaming/2_pipeline_bronze_multiplex.py` |
| Pipeline Silver Topics (standalone) | `dabs/src/streaming/3_pipeline_silver_topics.py` |
| Config DLT Ethereum | `dabs/resources/dlt/pipeline_ethereum.yml` |
| Config DLT App Logs | `dabs/resources/dlt/pipeline_app_logs.yml` |
| Databricks Bundle | `dabs/databricks.yml` |
| Workflows (batch, DDL, maint) | `dabs/resources/workflows/*.yml` |
| Batch scripts | `dabs/src/batch/batch_contracts/`, `ddl/`, `maintenance/`, `periodic/` |
| SCD Type 2 popular contracts | `dabs/src/batch/periodic/3_popular_contracts_scd2.py` |
| Workflow Full Refresh DLT | `dabs/resources/workflows/workflow_dlt_full_refresh.yml` |
| Lambda Ingestion | `lambda/contracts_ingestion/handler.py` |
| Terraform Lambda | `services/prd/10_lambda/lambda_contracts_ingestion.tf` |
| Scripts Ambiente | `scripts/environment/cleanup_s3.py`, `cleanup_dynamodb.py` |

---

## TODOs — Processamento de Dados

- [ ] **TODO-P01** 🔴 P0: Validar DLT triggered end-to-end em PROD. Configurado em `dabs/databricks.yml` (`prod` target), pendente validação E2E em ambiente PROD real. Blocker para validação do ambiente de produção (TODO-O12).
- [x] **TODO-P09**: ~~Avaliar migração do Airflow para MWAA~~ — Cancelado: Airflow removido. Orquestração migrada para Databricks Workflows + Lambda (EventBridge). Ver `docs/rearchitecting_airflow.md`.
