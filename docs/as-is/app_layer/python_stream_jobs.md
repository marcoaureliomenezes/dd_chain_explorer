# Jobs Python Streaming — Captura de Dados On-Chain em Tempo Real

## 1. Objetivo

Os Jobs Python Streaming são responsáveis por **capturar dados da blockchain Ethereum em tempo real** e publicá-los em tópicos Kafka para consumo downstream pelos Jobs Spark Streaming.

A conexão com a blockchain é feita via **Web3.py**, utilizando nós fornecidos por provedores de API (Alchemy, Infura) cujas chaves são armazenadas no **Azure Key Vault**.

---

## 2. Localização do Código

```
docker/app_layer/onchain-stream-txs/
├── Dockerfile
├── requirements.txt
└── src/
    ├── 1_mined_blocks_watcher.py     # Job 1: Detecta blocos minerados
    ├── 2_orphan_blocks_watcher.py    # Job 2: Detecta blocos órfãos
    ├── 3_block_data_crawler.py       # Job 3: Crawlea dados completos dos blocos
    ├── 4_mined_txs_crawler.py        # Job 4: Crawlea dados de transações
    ├── 4_txs_input_decoder.py        # Job 4b: Decodifica input de transações
    ├── configs/
    │   ├── producers.ini             # Configurações dos Kafka Producers
    │   └── consumers.ini             # Configurações dos Kafka Consumers
    ├── schemas/                      # Schemas Avro por tópico
    │   ├── 0_application_logs_avro.json
    │   ├── 1_mined_block_event_schema_avro.json
    │   ├── 2_block_data_schema_avro.json
    │   ├── 3_transaction_hash_ids_schema_avro.json
    │   └── 4_transactions_schema_avro.json
    └── utils/
        ├── api_keys_manager.py       # Gerenciamento de API Keys via Redis
        ├── get_secrets.py            # Leitura de segredos do Azure Key Vault
        ├── kafka_admin_client.py     # Administração de tópicos Kafka
        ├── kafka_utils.py            # Handlers de Kafka (producer/consumer Avro)
        └── web3_utils.py             # Conexão com nó Ethereum via Web3.py
```

---

## 3. Arquitetura do Pipeline de Streaming

O pipeline é composto por **4 jobs encadeados** que se comunicam **exclusivamente via tópicos Kafka**:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                  PIPELINE DE CAPTURA ON-CHAIN (STREAMING)                     │
│                                                                                │
│   BLOCKCHAIN ETHEREUM (Mainnet)                                               │
│         │                                                                      │
│    [Web3.py / Alchemy API]                                                    │
│         │                                                                      │
│         ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐             │
│   │  Job 1: MinedBlocksWatcher                                  │             │
│   │  • Polling da blockchain por novos blocos (clock freq: 1s)  │             │
│   │  • Publica: block_number, block_hash, timestamp             │             │
│   │  • Tópico: mainnet.1.mined_blocks.events                    │             │
│   └─────────────────────────────────────────┬───────────────────┘             │
│                                             │                                  │
│                                             ▼                                  │
│   ┌─────────────────────────────────────────────────────────────┐             │
│   │  Job 3: BlockDataCrawler                                    │             │
│   │  • Consome mainnet.1.mined_blocks.events                    │             │
│   │  • Busca dados completos do bloco via Web3.py               │             │
│   │  • Extrai lista de hashes de transações do bloco            │             │
│   │  • Publica dados do bloco: mainnet.2.blocks.data            │             │
│   │  • Publica hashes de txs: mainnet.3.block.txs.hash_id       │             │
│   └──────────┬──────────────────────────────┬───────────────────┘             │
│              │                              │                                  │
│              ▼                              ▼                                  │
│   ┌──────────────────────┐    ┌────────────────────────────────────────┐      │
│   │  mainnet.2.blocks.data│    │  Job 4: MinedTxsCrawler (N réplicas)   │      │
│   │  → Spark Streaming   │    │  • Consome mainnet.3.block.txs.hash_id  │      │
│   └──────────────────────┘    │  • Busca dados completos de cada tx     │      │
│                               │  • Até 8 réplicas paralelas             │      │
│                               │  • Publica: mainnet.4.transactions.data │      │
│                               └────────────────────────────────────────┘      │
│                                                                                │
│   ┌─────────────────────────────────────────────────────────────┐             │
│   │  Tópico de Logs: mainnet.0.application.logs                 │             │
│   │  • Todos os jobs publicam logs de aplicação aqui            │             │
│   │  • Consumido pelo Spark Streaming 1_api_key_monitor.py       │             │
│   └─────────────────────────────────────────────────────────────┘             │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Detalhamento dos Jobs

### 4.1 Job 1: `1_mined_blocks_watcher.py` — MinedBlocksWatcher

**Função:** Observa a blockchain Ethereum e detecta novos blocos minerados.

**Lógica:**
1. Conecta-se ao nó Ethereum via API do Alchemy (`Web3Handler.get_node_connection`)
2. Em loop contínuo: chama `get_block('latest')` com frequência configurável (`CLOCK_FREQUENCY`)
3. Quando detecta um bloco com número `N = prev_block + 1`, publica evento
4. Produz mensagem Avro no tópico `TOPIC_MINED_BLOCKS_EVENTS`

**Variáveis de ambiente:**
```bash
AKV_NODE_NAME=DataMasterNodeAsAService    # Nome do Key Vault para o nó
AKV_SECRET_NAME=alchemy-api-key-1         # Nome do segredo (API key)
TOPIC_LOGS=mainnet.0.application.logs
TOPIC_MINED_BLOCKS_EVENTS=mainnet.1.mined_blocks.events
CLOCK_FREQUENCY=1                          # Frequência de polling (segundos)
```

**Schema Avro publicado** (`1_mined_block_event_schema_avro.json`):
```json
{
  "block_timestamp": "int",
  "block_number": "int",
  "block_hash": "string"
}
```

---

### 4.2 Job 3: `3_block_data_crawler.py` — BlockDataCrawler

**Função:** Consome eventos de blocos e busca os dados completos de cada bloco.

**Lógica:**
1. Consome o tópico `mainnet.1.mined_blocks.events`
2. Para cada evento, chama `Web3Handler.extract_block_data(block_number)`
3. Parseia os dados com `Web3Handler.parse_block_data()` (converte HexBytes → str)
4. Extrai a lista de hashes de transações do bloco
5. Publica dados do bloco em `mainnet.2.blocks.data`
6. Para cada transação no bloco: publica o hash em `mainnet.3.block.txs.hash_id` (8 partições)

**Variáveis de ambiente:**
```bash
TOPIC_MINED_BLOCKS_EVENTS=mainnet.1.mined_blocks.events
TOPIC_MINED_BLOCKS=mainnet.2.blocks.data
TOPIC_TXS_HASH_IDS=mainnet.3.block.txs.hash_id
TOPIC_TXS_HASH_IDS_PARTITIONS=8
CONSUMER_GROUP=cg_block_data_crawler
TXS_PER_BLOCK=50
```

---

### 4.3 Job 4: `4_mined_txs_crawler.py` — MinedTxsCrawler

**Função:** Crawlea dados completos de transações a partir dos hashes.

**Lógica:**
1. Consome o tópico `mainnet.3.block.txs.hash_id` (grupo de consumer `cg_mined_raw_txs`)
2. Elege uma API Key disponível via `APIKeysManager.elect_new_api_key()`
3. Para cada hash de transação: chama `Web3Handler.extract_tx_data(tx_hash)`
4. Parseia com `Web3Handler.parse_transaction_data()`
5. Publica em `mainnet.4.transactions.data`

**Escalabilidade:** Este job pode ser deployado com **até 8 réplicas** (uma por partição do tópico de hashes).

**Variáveis de ambiente:**
```bash
TOPIC_TXS_HASH_IDS=mainnet.3.block.txs.hash_id
TOPIC_TXS_DATA=mainnet.4.transactions.data
CONSUMER_GROUP=cg_mined_raw_txs
AKV_NODE_SECRET_NAMES=infura-api-key-1-12   # Formato compactado: key-name-{inicio}-{fim}
```

---

## 5. Gerenciamento de API Keys

O projeto usa múltiplas API Keys de provedores de nós Ethereum (Alchemy e Infura) de forma concorrente. Para evitar conflitos e respeitar os limites de rate, existe um sistema de semáforo implementado com **Redis** e **Spark Streaming**.

### 5.1 Arquitetura do Sistema de Gerenciamento

```
┌─────────────────────────────────────────────────────────────────────────┐
│               SISTEMA DE GERENCIAMENTO DE API KEYS                      │
│                                                                         │
│  Azure Key Vault                                                        │
│  ├── alchemy-api-key-1     ──────────────────────────────────┐         │
│  ├── infura-api-key-1                                         │         │
│  ├── infura-api-key-2                                         │         │
│  └── infura-api-key-N     (pool de N API Keys)               │         │
│                                                               ▼         │
│  REDIS DB 1 (Semáforo — "quem está usando a chave")          │         │
│  ├── infura-api-key-1: {process: "pid_123", last_update: ts} │         │
│  └── infura-api-key-2: {process: "pid_456", last_update: ts} │         │
│                                                               │         │
│  REDIS DB 2 (Contador de consumo diário)                     │         │
│  ├── infura-api-key-1: {num_req_1d: 1420, end: "...", ...}   │         │
│  └── infura-api-key-2: {num_req_1d:  890, end: "...", ...}   │         │
│                                │                              │         │
│  ┌────────────────────────────────────────────────────────┐  │         │
│  │  Spark Streaming: 1_api_key_monitor.py                 │  │         │
│  │  • Consome tópico: mainnet.0.application.logs          │  │         │
│  │  • Filtra mensagens "API_request;{api_key_name}"        │  │         │
│  │  • Janela de 1 dia (count de requisições)              │  │         │
│  │  • Escreve contadores no REDIS DB 2                    │  │         │
│  └────────────────────────────────────────────────────────┘  │         │
│                                                               │         │
│  Jobs Python (4_mined_txs_crawler.py)                        │         │
│  • APIKeysManager.elect_new_api_key():                        │         │
│    1. Lê contadores do Redis DB 2 (ordenado por consumo)      │         │
│    2. Verifica Redis DB 1 (quais keys estão em uso)           │         │
│    3. Elege a key disponível com menor consumo                │         │
│    4. Registra no semáforo (Redis DB 1) com PID + timestamp   │         │
│    5. Após uso, libera a key (timeout automático: 15s)        │         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Classe `APIKeysManager`

```python
class APIKeysManager:
    def __init__(self, logger, pid, redis_client_1, redis_client_2, api_keys_compacted):
        # redis_client_1 → DB 1 (semáforo - quem usa a chave agora)
        # redis_client_2 → DB 2 (contador de consumo diário)
        # api_keys_compacted: formato "infura-api-key-1-12"
        #   → expande para ["infura-api-key-1", ..., "infura-api-key-12"]

    def elect_new_api_key(self):
        # 1. Ordena keys por consumo (Redis DB 2)
        # 2. Filtra as que não estão no semáforo (Redis DB 1)
        # 3. Retorna a primeira disponível

    def check_api_key_request(self, api_key):
        # Registra uso no semáforo com PID e timestamp atual

    def free_api_keys(self, free_timeout=15):
        # Libera keys cujo last_update > 15 segundos atrás

    def release_api_key_from_semaphore(self, api_key):
        # Remove a key do semáforo Redis DB 1
```

### 5.3 Formato Compactado de API Keys

Para facilitar a configuração, os nomes das API Keys seguem um formato compactado:

```
"infura-api-key-1-12"
→ expande para: ["infura-api-key-1", "infura-api-key-2", ..., "infura-api-key-12"]
```

Isso permite configurar um pool de 12 keys com uma única variável de ambiente.

### 5.4 Logging para Monitoramento

Todos os jobs Python publicam logs estruturados no tópico `mainnet.0.application.logs` usando o `KafkaLoggingHandler`. Para rastreamento de consumo de API, as mensagens seguem o padrão:

```
API_request;infura-api-key-3
API_KEY_ELECTED;infura-api-key-5
KEY_VAULT_REQUEST;alchemy-api-key-1
```

O Spark Streaming `1_api_key_monitor.py` parseia essas mensagens e mantém contadores no Redis.

---

## 6. Schemas Avro e Schema Registry

Todos os dados publicados no Kafka usam serialização **Avro** gerenciada pelo Confluent Schema Registry.

| Tópico                              | Schema Avro                              |
|-------------------------------------|------------------------------------------|
| `mainnet.0.application.logs`        | `0_application_logs_avro.json`           |
| `mainnet.1.mined_blocks.events`     | `1_mined_block_event_schema_avro.json`   |
| `mainnet.2.blocks.data`             | `2_block_data_schema_avro.json`          |
| `mainnet.3.block.txs.hash_id`       | `3_transaction_hash_ids_schema_avro.json`|
| `mainnet.4.transactions.data`       | `4_transactions_schema_avro.json`        |

Os producers utilizam `KafkaHandler.create_avro_producer()` da lib `dm-33-utils`, que integra com o Schema Registry para registrar/validar schemas automaticamente.

---

## 7. Deploy

### Docker Compose (desenvolvimento):

```yaml
# python_streaming_apps_layer.yml
python-job-mined-blocks-watcher:
  <<: *conf_dev_onchain_stream_txs
  environment:
    AKV_NODE_NAME: DataMasterNodeAsAService
    AKV_SECRET_NAME: 'alchemy-api-key-1'
    TOPIC_MINED_BLOCKS_EVENTS: mainnet.1.mined_blocks.events
    CLOCK_FREQUENCY: 1
```

```bash
make deploy_dev_apps
```

### Docker Swarm (produção):

```bash
# As imagens são referenciadas nas DAGs do Airflow via DockerOperator
# ou deployadas manualmente como serviços Swarm
make build_apps
make publish_apps
```

---

## 8. Adaptações Necessárias para a Cloud

| Item                             | On-premises                        | Cloud (AWS)                               | Adaptação Necessária                           |
|----------------------------------|------------------------------------|-------------------------------------------|------------------------------------------------|
| Nó Ethereum                      | Alchemy/Infura via Azure KV        | Alchemy/Infura via AWS Secrets Manager    | Substituir `az-identity` por `boto3` (AWS SSM) |
| Kafka Broker                     | `broker-1:29092`                   | Amazon MSK endpoint                       | Alterar `KAFKA_BROKERS` env var                |
| Schema Registry                  | `schema-registry:8081`             | AWS Glue Schema Registry                  | Adaptar `KafkaHandler` para Glue               |
| Redis (semáforo)                 | `redis:6379`                       | Amazon ElastiCache for Redis              | Alterar `REDIS_HOST`/`REDIS_PORT` env vars     |
| Azure Key Vault                  | `SecretClient` + `DefaultAzureCredential` | AWS Secrets Manager (`boto3`)       | Substituir `get_secrets.py`                    |
| Deploy dos containers            | Docker Swarm                       | Amazon ECS (Fargate)                      | Criar task definitions ECS                     |
| Logging                          | Kafka logs topic                   | Amazon CloudWatch Logs + MSK topic        | Adicionar `CloudWatchLoggingHandler`           |
