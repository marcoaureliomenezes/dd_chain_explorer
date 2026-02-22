# Ambiente de Desenvolvimento

Este documento descreve a estrutura da aplicacao `onchain-stream-txs`, a configuracao da imagem Docker e como ela se conecta aos servicos perifericos no ambiente de desenvolvimento local.

---

## Estrutura do Projeto

```
docker/onchain-stream-txs/
  Dockerfile
  requirements.txt
  src/
    1_mined_blocks_watcher.py       # Job 1 - Deteccao de blocos minerados
    2_orphan_blocks_watcher.py      # Job 2 - Deteccao de blocos orfaos
    3_block_data_crawler.py         # Job 3 - Captura de dados de blocos
    4_mined_txs_crawler.py          # Job 4 - Captura de transacoes brutas
    5_txs_input_decoder.py          # Job 5 - Decodificacao de input de transacoes
    n_semaphore_collect.py          # Utilitario - Exibicao do estado dos semaforos
    chain_extractor.py              # Classe base abstrata para jobs de streaming
    configs/
      producers.ini                 # Configuracoes de producers Kafka
      consumers.ini                 # Configuracoes de consumers Kafka
      topics.ini                    # Definicao de topicos Kafka
    schemas/
      0_application_logs_avro.json
      1_mined_block_event_schema_avro.json
      2_block_data_schema_avro.json
      3_transaction_hash_ids_schema_avro.json
      4_transactions_schema_avro.json
      txs_contract_call_decoded.json
    utils/
      api_keys_manager.py           # Gerenciamento de API keys com semaforo Redis
      dm_parameter_store.py         # Cliente AWS SSM Parameter Store
      dm_redis.py                   # Wrapper Redis (DEV local / PROD ElastiCache)
      etherscan_utils.py            # Cliente Etherscan com cache em disco
      kafka_utils.py                # Producers e consumers AVRO Kafka
      logger_utils.py               # Handler de logging via Kafka
      schema_registry_utils.py      # Abstracaoo de Schema Registry (DEV/PROD)
      web3_utils.py                 # Conexao com nos Ethereum via Web3.py
```

Cada arquivo `N_*.py` representa um job de streaming independente. Todos herdam de `ChainExtractor`, uma classe abstrata que define a interface `src_config` / `sink_config` / `run` e fornece o metodo utilitario `consuming_topic` para iterar sobre mensagens Kafka.

---

## Imagem Docker

O `Dockerfile` utiliza `python:3.12-slim` como base:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY ./requirements.txt /app
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY ./src /app
ENTRYPOINT [ "sleep", "infinity" ]
```

O entrypoint padrao (`sleep infinity`) e substituido em tempo de execucao pelo `docker-compose` (`app_services.yml`), que define o comando real para cada job. Isso permite que todos os jobs compartilhem a mesma imagem.

### Dependencias principais (`requirements.txt`)

| Pacote | Versao | Funcao |
|--------|--------|--------|
| `web3` | 7.8.0 | Conexao com nos Ethereum (Alchemy, Infura) |
| `confluent-kafka` | 2.6.0 | Producer/consumer Kafka com serialzacao AVRO |
| `fastavro` | 1.10.0 | Serializacao/desserializacao AVRO |
| `redis` | 5.2.1 | Acesso ao Redis (semaforo, cache) |
| `boto3` | >=1.26.0 | Acesso ao AWS SSM Parameter Store |
| `requests` | 2.28.1 | Chamadas HTTP (Etherscan, 4byte.directory) |
| `dm-33-utils` | 0.0.5 | Biblioteca interna com utilitarios (conversao HexBytes, etc.) |

---

## Servicos Perifericos (Ambiente Local)

O ambiente de desenvolvimento replica localmente os servicos gerenciados da AWS. Os containers sao orquestrados via Docker Compose em dois arquivos:

- `services/local_services.yml` -- infraestrutura local (Kafka, Redis, Spark)
- `services/app_services.yml` -- jobs de streaming Python e Spark

### Inicializacao

```bash
# Criar a rede compartilhada
docker network create vpc_dm

# Subir infraestrutura local
docker compose -f services/local_services.yml up -d

# Subir jobs de streaming
docker compose -f services/app_services.yml up -d
```

### Diagrama de conectividade

```
+---------------------+     +---------------------+     +---------------------+
|  kafka-broker-1     |     |  schema-registry    |     |  redis              |
|  (Confluent 7.6.0)  |     |  (Confluent 7.6.0)  |     |  (Redis 7 Alpine)   |
|  Porta: 9092/29092  |     |  Porta: 8081        |     |  Porta: 6379        |
+---------------------+     +---------------------+     +---------------------+
         |                           |                           |
         +---------------------------+---------------------------+
                                     |
                          rede: vpc_dm (bridge)
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
   Jobs Python (1-5)          Spark Master/Worker      control-center (9021)
   (app_services.yml)         (local_services.yml)     (local_services.yml)
```

---

## Configuracao de Kafka

Os jobs se conectam ao Kafka usando variaveis de ambiente definidas em `services/conf/local.kafka.conf`:

```properties
NETWORK=mainnet
KAFKA_BROKERS=kafka-broker-1:9092
SCHEMA_REGISTRY_URL=http://schema-registry:8081
```

As configuracoes detalhadas de producers e consumers estao nos arquivos `.ini` que cada job recebe como argumento na linha de comando:

**`configs/producers.ini`** -- configuracoes de entrega garantida:
```ini
[producer.general.config]
acks=all
retries=3
enable.idempotence=true
```

**`configs/consumers.ini`** -- configuracoes de consumo:
```ini
[consumer.general.config]
enable.auto.commit=true
auto.offset.reset=earliest
auto.commit.interval.ms=1000
```

### Schema Registry

Em desenvolvimento, o Schema Registry e uma instancia local do Confluent Schema Registry. O modulo `schema_registry_utils.py` detecta o ambiente via `APP_ENV`:

- `APP_ENV=dev` (padrao): usa o Confluent Schema Registry local, registrando automaticamente schemas a partir dos arquivos `.json` em `schemas/` caso ainda nao existam.
- `APP_ENV=prod`: usa o AWS Glue Schema Registry (detalhado em [2_environment_prod.md](2_environment_prod.md)).

---

## Configuracao de Redis

Os jobs usam Redis para tres finalidades distintas, cada uma em um database separado:

| Database | Variavel de ambiente | Funcao |
|----------|---------------------|--------|
| `db=0` | `REDIS_DB_APK_SEMAPHORE` | Semaforo distribuido de API keys |
| `db=1` | `REDIS_DB_APK_COUNTER` | Contadores de requisicoes por API key |
| `db=2` | `REDIS_DB_BLOCK_CACHE` | Cache de hashes de blocos (deteccao de orfaos) |
| `db=3` | `REDIS_DB_SEMAPHORE_DISPLAY` | Snapshot do estado dos semaforos para monitoramento |

As variaveis de conexao sao definidas em `services/conf/dev.redis.conf`:

```properties
REDIS_HOST=redis
REDIS_PORT=6379
APP_ENV=dev
```

O wrapper `dm_redis.py` detecta `APP_ENV=dev` e conecta sem TLS e sem autenticacao. Em producao, o mesmo wrapper ativa TLS automaticamente (ver [2_environment_prod.md](2_environment_prod.md)).

---

## Configuracao de AWS (Credenciais)

Mesmo em ambiente local, os jobs precisam de credenciais AWS reais para acessar o SSM Parameter Store (onde as API keys dos provedores Web3 estao armazenadas). O `docker-compose` monta o diretorio de credenciais do host:

```yaml
volumes:
  - ~/.aws:/root/.aws:ro
```

Isso permite que o `boto3` dentro dos containers utilize o perfil configurado no host. A regiao padrao e `sa-east-1`.

### Hierarquia de parametros SSM

As API keys estao organizadas no SSM Parameter Store conforme a hierarquia:

```
/web3-api-keys/
  alchemy/
    api-key-1
    api-key-2
    api-key-3
    api-key-4
  infura/
    api-key-1
    api-key-2
    ...
    api-key-17
/etherscan-api-keys/
  api-key-1
  api-key-2
  ...
  api-key-5
```

Detalhes sobre o gerenciamento de API keys em [4_api_key_management.md](4_api_key_management.md).

---

## Variaveis de Ambiente por Job

A tabela abaixo consolida as variaveis de ambiente de cada servico conforme definidas em `app_services.yml`:

| Variavel | Job 1 | Job 2 | Job 3 | Job 4 | Job 5 |
|----------|-------|-------|-------|-------|-------|
| `NETWORK` | mainnet | mainnet | mainnet | mainnet | mainnet |
| `KAFKA_BROKERS` | (env file) | (env file) | (env file) | (env file) | (env file) |
| `SCHEMA_REGISTRY_URL` | (env file) | (env file) | (env file) | (env file) | (env file) |
| `TOPIC_LOGS` | mainnet.0.application.logs | mainnet.0.application.logs | mainnet.0.application.logs | mainnet.0.application.logs | mainnet.0.application.logs |
| `TOPIC_MINED_BLOCKS_EVENTS` | mainnet.1.mined_blocks.events | mainnet.1.mined_blocks.events | mainnet.1.mined_blocks.events | -- | -- |
| `TOPIC_MINED_BLOCKS` | -- | -- | mainnet.2.blocks.data | -- | -- |
| `TOPIC_TXS_HASH_IDS` | -- | -- | mainnet.3.block.txs.hash_id | mainnet.3.block.txs.hash_id | -- |
| `TOPIC_TXS_DATA` | -- | -- | -- | mainnet.4.transactions.data | mainnet.4.transactions.data |
| `TOPIC_TXS_DECODED` | -- | -- | -- | -- | mainnet.5.transactions.input_decoded |
| `AKV_SECRET_NAME` | /web3-api-keys/alchemy/api-key-1 | /web3-api-keys/alchemy/api-key-2 | /web3-api-keys/alchemy/api-key-2 | -- | -- |
| `AKV_SECRET_NAMES` | -- | -- | -- | /web3-api-keys/infura/api-key-1-17 | -- |
| `SSM_ETHERSCAN_KEY` | -- | -- | -- | -- | /etherscan-api-keys/api-key-1 |
| `CONSUMER_GROUP` | -- | cg_orphan_block_events | cg_block_data_crawler | cg_mined_raw_txs | cg_txs_input_decoder |
| `CLOCK_FREQUENCY` | 1 | -- | -- | -- | -- |
| `TXS_PER_BLOCK` | -- | -- | 50 | -- | -- |
| Replicas | 1 | 1 | 1 | 6 | 1 |

---

## Logging

Todos os jobs enviam seus logs para o topico Kafka `mainnet.0.application.logs` por meio do `KafkaLoggingHandler` (definido em `utils/logger_utils.py`). Cada registro de log e serializado em AVRO com o schema `0_application_logs_avro.json` e contem:

- `timestamp` -- epoch em segundos
- `logger` -- nome do logger (ex: `MINED_BLOCKS_EVENTS`)
- `level` -- nivel do log (`INFO`, `ERROR`, etc.)
- `filename` -- arquivo de origem
- `function_name` -- funcao de origem
- `message` -- mensagem formatada

Esse topico de logs e consumido pelo job Spark `1_api_key_monitor.py` para calcular metricas de consumo de API keys (ver [4_api_key_management.md](4_api_key_management.md)).