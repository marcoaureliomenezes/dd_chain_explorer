# onchain-stream-txs

Pipeline de streaming para captura e processamento de transacoes da rede Ethereum mainnet em tempo real.

## Descricao

Este modulo contem um conjunto de 5 jobs Python que operam em cadeia sobre o Apache Kafka, formando um pipeline completo de ingestao de dados on-chain. O pipeline detecta novos blocos minerados, identifica reorganizacoes de cadeia (blocos orfaos), coleta dados brutos de blocos e transacoes via provedores Web3 (Alchemy e Infura), e decodifica as chamadas a contratos inteligentes (campo `input`) utilizando ABIs do Etherscan e assinaturas do 4byte.directory.

Todos os dados sao serializados em formato AVRO com schemas registrados em um Schema Registry, garantindo compatibilidade e evolucao controlada dos schemas entre os jobs.

O pipeline e projetado para operar tanto em ambiente local (Docker Compose) quanto em producao na AWS (ECS Fargate + MSK + ElastiCache).

---

## Pipeline de dados

```
  Ethereum mainnet
       |
       v
  [Job 1] Mined Blocks Watcher       -- detecta blocos minerados via polling RPC
       |
       v
  [Job 2] Orphan Blocks Watcher      -- verifica reorganizacoes de cadeia
  [Job 3] Block Data Crawler          -- captura dados do bloco e lista transacoes
       |
       v
  [Job 4] Raw Transactions Crawler    -- captura dados brutos de cada transacao (x6 replicas)
       |
       v
  [Job 5] Transaction Input Decoder   -- decodifica chamadas a contratos inteligentes
```

Adicionalmente, um job Spark Structured Streaming monitora o consumo de API keys agregando logs em janelas temporais diarias.

---

## Tecnologias

- **Linguagem**: Python 3.12
- **Mensageria**: Apache Kafka (Confluent KRaft 7.6 em DEV, Amazon MSK em PROD)
- **Serializacao**: Apache AVRO com Confluent Schema Registry / AWS Glue Schema Registry
- **Cache distribuido**: Redis 7 (standalone em DEV, ElastiCache com TLS em PROD)
- **Provedores Web3**: Alchemy (WebSocket), Infura (HTTPS)
- **Decodificacao**: Etherscan API + 4byte.directory
- **Armazenamento de segredos**: AWS Systems Manager Parameter Store
- **Processamento**: Apache Spark Structured Streaming (monitoramento)
- **Infraestrutura**: Docker Compose (DEV), ECS Fargate + Terraform (PROD)

---

## Documentacao detalhada

| Documento | Conteudo |
|-----------|----------|
| [1. Ambiente de Desenvolvimento](docs/1_environment_dev.md) | Estrutura do projeto, imagem Docker, dependencias, configuracao dos servicos locais (Kafka, Redis, Schema Registry), variaveis de ambiente e sistema de logging |
| [2. Ambiente de Producao](docs/2_environment_prod.md) | Arquitetura AWS, ECS Fargate, Amazon MSK, Glue Schema Registry, ElastiCache, SSM Parameter Store, Terraform e diferencas em relacao ao ambiente de desenvolvimento |
| [3. Captura de Transacoes On-Chain](docs/3_capture_chain_txs.md) | Descricao tecnica de cada job de streaming, topicos Kafka, formatos de dados AVRO, fluxo de dados entre jobs, classe base `ChainExtractor` e estrategia de decodificacao do campo `input` |
| [4. Gerenciamento de API Keys](docs/4_api_key_management.md) | Hierarquia SSM, semaforo distribuido Redis, algoritmo de eleicao e rotacao de keys, logging de consumo, monitoramento via Spark e teste de validade das keys |

---

## Execucao rapida (DEV)

```bash
# Subir servicos de infraestrutura (Kafka, Redis, Schema Registry)
docker compose -f services/local_services.yml up -d

# Subir jobs de streaming
docker compose -f services/app_services.yml up -d
```

---

## Estrutura de diretorios

```
docker/onchain-stream-txs/
  Dockerfile              # Imagem base python:3.12-slim
  requirements.txt        # Dependencias Python
  README.md               # Este arquivo
  docs/                   # Documentacao detalhada
  src/
    1_mined_blocks_watcher.py
    2_orphan_blocks_watcher.py
    3_block_data_crawler.py
    4_mined_txs_crawler.py
    5_txs_input_decoder.py
    chain_extractor.py        # Classe abstrata base
    n_semaphore_collect.py    # Snapshot do semaforo Redis
    configs/                  # producers.ini, consumers.ini, topics.ini
    schemas/                  # Schemas AVRO (6 arquivos)
    utils/                    # Modulos utilitarios
      api_keys_manager.py     # Semaforo distribuido de API keys
      dm_redis.py             # Wrapper Redis (DEV/PROD)
      dm_parameter_store.py   # Cliente AWS SSM
      etherscan_utils.py      # ABI cache + 4byte fallback
      kafka_utils.py          # Serializacao AVRO + Producer/Consumer
      logger_utils.py         # Logging estruturado via Kafka
      schema_registry_utils.py # Confluent SR / AWS Glue
      web3_utils.py           # Conexao RPC + parsing de blocos/txs
  test/
```