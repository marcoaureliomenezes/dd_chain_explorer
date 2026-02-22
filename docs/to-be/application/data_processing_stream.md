# Processamento Streaming — Delta Live Tables (DLT)

## Visão Geral

O processamento de dados em streaming é realizado pelo **Databricks Delta Live Tables (DLT)**. Cada pipeline DLT roda em modo **contínuo** — assim que novos dados chegam ao Kafka ou à camada Bronze, são processados e persistidos na camada Silver correspondente.

Esta abordagem substitui os jobs Spark Streaming do AS-IS, que eram gerenciados manualmente via Docker Swarm.

---

## Topologia de Pipelines

```
Kafka (MSK)
    │
    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ DLT: dm-bronze-multiplex                                              │
│ Notebook: src/streaming/2_pipeline_bronze_multiplex.py               │
│                                                                       │
│ Consome: todos os 5 tópicos Kafka                                     │
│ Produz:  b_fast.kafka_topics_multiplexed                              │
└────────────────────────┬──────────────────────────────────────────────┘
                         │
          ┌──────────────┼────────────────────────────────┐
          │              │                                │
          ▼              ▼                                ▼
┌──────────────┐ ┌──────────────────┐ ┌──────────────────────────────────┐
│ DLT: Silver  │ │ DLT: Silver      │ │ DLT: Silver Blocks +             │
│ Apps Logs    │ │ Blocks Events    │ │      Silver Transactions          │
│ (s_logs)     │ │ (s_apps)         │ │ (s_apps)                         │
└──────────────┘ └──────────────────┘ └──────────────────────────────────┘
```

---

## Pipeline 1 — Bronze Multiplex (`dm-bronze-multiplex`)

**Arquivo:** `dabs/resources/dlt/pipeline_bronze_multiplex.yml`  
**Notebook:** `dabs/src/streaming/2_pipeline_bronze_multiplex.py`  
**Target:** `b_fast`  
**Modo:** contínuo

### O que faz

Consome todos os 5 tópicos Kafka via Structured Streaming e grava os registros crus na tabela Bronze `b_fast.kafka_topics_multiplexed`.

É a única pipeline que lê diretamente do Kafka. As demais pipelines Silver consomem desta tabela Bronze.

### Configurações

```yaml
kafka.bootstrap.servers: ${var.kafka_bootstrap_servers}
kafka.msk.iam.auth: "true"           # autenticação IAM no MSK
spark.sql.extensions: io.delta.sql.DeltaSparkSessionExtension
```

### Tabela produzida

**`b_fast.kafka_topics_multiplexed`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `topic_name` | STRING | Nome do tópico Kafka (partition key) |
| `partition` | INT | Partição Kafka |
| `offset` | BIGINT | Offset da mensagem |
| `timestamp` | TIMESTAMP | Timestamp da mensagem |
| `key` | STRING | Chave da mensagem |
| `value` | STRING | Valor da mensagem (JSON serializado) |

---

## Pipeline 2 — Silver Apps Logs (`dm-silver-apps-logs`)

**Arquivo:** `dabs/resources/dlt/pipeline_silver_layers.yml`  
**Notebook:** `dabs/src/streaming/3_pipeline_silver_apps_logs.py`  
**Source:** `b_fast.kafka_topics_multiplexed`  
**Target:** `s_logs`  
**Modo:** contínuo

### O que faz

Filtra os registros do tópico `mainnet.0.application.logs` da tabela Bronze e os parseia para a estrutura tipada de logs de aplicação.

### Tabela produzida

**`s_logs.apps_logs_fast`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `level` | STRING | Nível do log (`INFO`, `WARN`, `ERROR`) |
| `logger` | STRING | Nome da aplicação que gerou o log |
| `message` | STRING | Mensagem do log |
| `timestamp` | BIGINT | Timestamp epoch |
| `job_name` | STRING | Nome do job (partition key) |
| `api_key` | STRING | Chave de API em uso (quando aplicável) |
| `event_time` | TIMESTAMP | Timestamp processado |
| `kafka_timestamp` | TIMESTAMP | Timestamp original do Kafka |

---

## Pipeline 3 — Silver Blocks Events (`dm-silver-blocks-events`)

**Arquivo:** `dabs/resources/dlt/pipeline_silver_layers.yml`  
**Notebook:** `dabs/src/streaming/4_pipeline_silver_blocks_events.py`  
**Source:** `b_fast.kafka_topics_multiplexed`  
**Target:** `s_apps`  
**Modo:** contínuo

### O que faz

Filtra e parseia os registros do tópico `mainnet.1.mined_blocks.events` — eventos leves de blocos minerados publicados pelo `mined_blocks_watcher`.

### Tabela produzida

**`s_apps.mined_blocks_events`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `block_number` | BIGINT | Número do bloco (NOT NULL) |
| `block_hash` | STRING | Hash do bloco |
| `parent_hash` | STRING | Hash do bloco pai |
| `block_timestamp` | BIGINT | Timestamp Unix do bloco |
| `transaction_count` | INT | Número de transações no bloco |
| `event_time` | TIMESTAMP | Timestamp processado |
| `kafka_timestamp` | TIMESTAMP | Timestamp original do Kafka |

Change Data Feed habilitado (`delta.enableChangeDataFeed = true`).

---

## Pipeline 4 — Silver Blocks (`dm-silver-blocks`)

**Arquivo:** `dabs/resources/dlt/pipeline_silver_layers.yml`  
**Notebook:** `dabs/src/streaming/5_pipeline_silver_blocks.py`  
**Source:** `b_fast.kafka_topics_multiplexed`  
**Target:** `s_apps`  
**Modo:** contínuo

### O que faz

Parseia os dados completos dos blocos (`mainnet.2.blocks.data`) publicados pelo `block_data_crawler`.

### Tabela produzida

**`s_apps.blocks_fast`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `number` | BIGINT | Número do bloco |
| `hash` | STRING | Hash do bloco |
| `parent_hash` | STRING | Hash do bloco pai |
| `timestamp` | BIGINT | Timestamp Unix |
| `miner` | STRING | Endereço do minerador |
| `difficulty` | BIGINT | Dificuldade do bloco |
| `total_difficulty` | STRING | Dificuldade acumulada |
| `size` | INT | Tamanho em bytes |
| `gas_used` | BIGINT | Gas utilizado |
| `gas_limit` | BIGINT | Limite de gas do bloco |
| `transaction_count` | INT | Número de transações |
| `base_fee_per_gas` | BIGINT | Base fee (EIP-1559) |
| `event_time` | TIMESTAMP | Timestamp processado |
| `kafka_timestamp` | TIMESTAMP | Timestamp original do Kafka |

Change Data Feed habilitado.

---

## Pipeline 5 — Silver Transactions (`dm-silver-transactions`)

**Arquivo:** `dabs/resources/dlt/pipeline_silver_layers.yml`  
**Notebook:** `dabs/src/streaming/6_pipeline_silver_transactions.py`  
**Source:** `b_fast.kafka_topics_multiplexed`  
**Target:** `s_apps`  
**Modo:** contínuo  
**Workers:** 2 (maior carga de dados)

### O que faz

Parseia as transações completas (`mainnet.4.transactions.data`) publicadas pelas 8 réplicas do `mined_txs_crawler`.

### Tabela produzida

**`s_apps.transactions_fast`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `hash` | STRING | Hash da transação |
| `block_number` | BIGINT | Número do bloco (partition key) |
| `block_hash` | STRING | Hash do bloco |
| `transaction_index` | INT | Índice na lista do bloco |
| `from_address` | STRING | Endereço do remetente |
| `to_address` | STRING | Endereço do destinatário (contrato ou EOA) |
| `value` | STRING | Valor em Wei (string para evitar overflow) |
| `gas` | BIGINT | Gas limit da transação |
| `gas_price` | BIGINT | Preço do gas em Wei |
| `nonce` | BIGINT | Nonce do remetente |
| `input` | STRING | Input data (calldata) |
| `type` | INT | Tipo de transação (0=legacy, 2=EIP-1559) |
| `max_fee_per_gas` | BIGINT | Max fee (EIP-1559) |
| `max_priority_fee_per_gas` | BIGINT | Max priority fee (EIP-1559) |
| `kafka_timestamp` | TIMESTAMP | Timestamp original do Kafka |

Change Data Feed habilitado. Particionado por `block_number`.

---

## Configuração dos Pipelines

### Cluster padrão (todos os pipelines)

```yaml
spark_version: 15.4.x-scala2.12
node_type_id:  i3.xlarge
num_workers:   1  (exceto dm-silver-transactions: 2)
```

### Modo `development`

Em DEV (`--target dev`), os pipelines rodam em modo `development: true`, o que habilita:
- Visualização de erros mais detalhada
- Dados de desenvolvimento isolados (sem impactar PROD)

---

## Como Operar

### Verificar status dos pipelines

```bash
# Via CLI Databricks
databricks pipelines list

# Via DABs
make dabs_status_dev
```

### Reiniciar um pipeline (reprocessar do início)

Pelo Databricks UI: **Pipelines → Selecionar → Full Refresh**

Ou via CLI:
```bash
databricks pipelines start --pipeline-id <id> --full-refresh
```

### Monitorar métricas

As tabelas são monitoradas pelo workflow `dm-iceberg-maintenance` (step `monitor_tables`), que registra row count e tamanho das tabelas diariamente.

Consulte [jobs.md](../workflows/jobs.md) para detalhes do workflow de manutenção.
