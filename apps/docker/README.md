# apps/docker — Streaming Apps (onchain-stream-txs)

Aplicações Python de captura de dados on-chain da rede Ethereum, empacotadas em uma única imagem Docker e executadas como serviços independentes.

---

## Visão Geral

Pipeline de 5 jobs que operam em cadeia. Jobs 3 e 5 publicam dados diretamente no **Firehose Direct Put** (sem Kinesis); Jobs 2 e 4 publicam em **Kinesis Data Streams** (`mainnet-transactions-data`). Coordenação inter-job via **AWS SQS**:

```
Ethereum RPC (Alchemy / Infura)
        │
        ▼
┌─────────────────────────┐
│ Job 1: Mined Blocks      │  polling a cada N segundos
│ Watcher                  │
└─────────────┬───────────┘
              │ SQS: mainnet-mined-blocks-events
       ┌──────┴──────┐
       ▼             ▼
┌──────────┐  ┌──────────────────┐
│ Job 2:   │  │ Job 3:           │
│ Orphan   │  │ Block Data       │
│ Blocks   │  │ Crawler          │
└──────────┘  └────────┬─────────┘
                       │ Firehose Direct Put: firehose-mainnet-blocks-data
                       │ SQS: mainnet-block-txs-hash-id
                       ▼
              ┌──────────────────┐
              │ Job 4:           │  ×6 réplicas
              │ Raw Txs Crawler  │
              └────────┬─────────┘
                       │ Kinesis: mainnet-transactions-data
                       ▼
              ┌──────────────────┐
              │ Job 5:           │
              │ Tx Input Decoder │
              └────────┬─────────┘
                       │ Firehose Direct Put: firehose-mainnet-txs-decoded
                       ▼
              CloudWatch Logs (todos os jobs)
```

---

## Estrutura

```
apps/docker/onchain-stream-txs/
  Dockerfile
  requirements.txt
  src/
    1_mined_blocks_watcher.py     # Job 1 — Detecção de blocos minerados
    2_orphan_blocks_watcher.py    # Job 2 — Detecção de blocos órfãos
    3_block_data_crawler.py       # Job 3 — Captura de dados de blocos
    4_mined_txs_crawler.py        # Job 4 — Captura de transações (×6 réplicas)
    5_txs_input_decoder.py        # Job 5 — Decodificação de calldata
    configs/
      producers.ini               # Configurações de producers Kinesis
      consumers.ini               # Configurações de consumers SQS
      topics.ini                  # Definição de streams/queues
    schemas/                      # Schemas JSON para validação de payloads
    utils_decode/
      abi_cache.py                # Cache de ABIs de contratos (LRU + disco)
      etherscan_multi.py          # Cliente Etherscan com múltiplas API keys
```

---

## Imagem Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY ./requirements.txt /app
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY ./src /app
ENTRYPOINT [ "sleep", "infinity" ]
```

O `ENTRYPOINT` padrão (`sleep infinity`) é substituído em runtime pelo Docker Compose ou ECS task definition com o comando real de cada job.

### Dependências principais

| Pacote | Função |
|--------|--------|
| `web3` | Conexão com nós Ethereum (Alchemy, Infura) |
| `boto3` | Kinesis, SQS, SSM Parameter Store, DynamoDB, CloudWatch Logs |
| `dm-chain-utils` | Biblioteca interna — utilitários compartilhados |
| `requests` | Chamadas HTTP (Etherscan, 4byte.directory) |

---

## Ambiente DEV — Docker Compose

Os jobs conectam a recursos AWS reais (Kinesis, SQS, DynamoDB, SSM) usando as credenciais do host.

```bash
# Subir todos os jobs
make deploy_dev_stream

# Parar
make stop_dev_stream

# Monitorar
make watch_dev_stream
```

Arquivo de compose: `services/dev/00_compose/app_services.yml`

### Variáveis de ambiente por job

| Variável | Job 1 | Job 2 | Job 3 | Job 4 | Job 5 |
|----------|-------|-------|-------|-------|-------|
| `NETWORK` | mainnet | mainnet | mainnet | mainnet | mainnet |
| `KINESIS_STREAM_MINED_BLOCKS` | sink | src+sink | src | — | — |
| `FIREHOSE_STREAM_BLOCKS` | — | — | sink (Direct Put) | — | — |
| `KINESIS_STREAM_TXS_DATA` | — | — | — | sink | src |
| `FIREHOSE_STREAM_DECODED` | — | — | — | — | sink (Direct Put) |
| `SQS_QUEUE_TXS_HASH_ID` | — | — | sink | src | — |
| `SSM_SECRET_NAME` | api-key-1 | api-key-2 | api-key-2 | — | — |
| `SSM_SECRET_NAMES` | — | — | — | infura-1-17 | — |
| `SSM_ETHERSCAN_PATH` | — | — | — | — | /etherscan-api-keys |
| `DYNAMODB_TABLE` | — | BLOCK_CACHE | — | SEMAPHORE | — |
| `CLOCK_FREQUENCY` | 1s | — | — | — | — |
| `TXS_PER_BLOCK` | — | — | 50 | — | — |
| Réplicas | 1 | 1 | 1 | 6 | 1 |

---

## Ambiente PROD — ECS Fargate

Em produção, cada job é um ECS service no cluster `dm-chain-explorer-ecs`.

| ECS Service | Job |
|-------------|-----|
| `dm-mined-blocks-watcher` | Job 1 |
| `dm-orphan-blocks-watcher` | Job 2 |
| `dm-block-data-crawler` | Job 3 |
| `dm-mined-txs-crawler` | Job 4 (6 tasks) |
| `dm-txs-input-decoder` | Job 5 |

Infraestrutura provisionada por Terraform em `services/prd/07_ecs/`.  
Deploy via CI/CD: `.github/workflows/deploy_all_dm_applications.yml` (streaming apps):

---

## Gerenciamento de API Keys

Os jobs fazem polling de nós Ethereum via Alchemy (Jobs 1–3) e Infura (Job 4), com as API keys armazenadas no **SSM Parameter Store**:

```
/web3-api-keys/
  alchemy/api-key-{1..4}
  infura/api-key-{1..17}
/etherscan-api-keys/api-key-{1..5}
```

O Job 4 usa um **semáforo distribuído DynamoDB** (`PK=SEMAPHORE`) para coordenar o uso de API keys entre as 6 réplicas, evitando rate-limiting.

---

## Build Manual

```bash
make build_stream VERSION=1.0.0
make push_stream  VERSION=1.0.0
```

Em CI/CD, a imagem é construída e publicada no ECR automaticamente com tag `{SHA}` pelo workflow `deploy_all_dm_applications.yml`.
