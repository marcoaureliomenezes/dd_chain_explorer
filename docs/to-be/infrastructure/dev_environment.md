# Ambiente de Desenvolvimento (DEV)

## Visão Geral

O ambiente de desenvolvimento replica localmente os recursos AWS que estariam em produção, permitindo testar as aplicações Python e os notebooks DABs sem custo de cloud.

| Recurso em PROD | Equivalente local |
|-----------------|-------------------|
| Amazon MSK (Kafka) | `kafka-broker-1` (Confluent `cp-server:7.6.0`) |
| AWS Glue Schema Registry | `schema-registry` (Confluent `cp-schema-registry:7.6.0`) |
| Amazon DynamoDB | `dynamodb-local` (`amazon/dynamodb-local:2.4.0`) |
| Databricks (processamento) | Databricks Free Edition (via DABs CLI) |
| ECS Fargate (apps Python) | Docker Compose local |

---

## Pré-requisitos

- Docker Engine >= 24
- Docker Compose v2 (`docker compose`)
- Databricks CLI >= 0.218.0 (`pip install databricks-cli`)
- Python 3.10+
- `make`

---

## Estrutura de Arquivos Compose

```
services/compose/
├── local_services.yml            # Kafka + DynamoDB (infraestrutura local)
├── python_streaming_apps_layer.yml  # Apps Python de captura on-chain
└── conf/
    ├── dev.dynamodb.conf         # Variáveis para DynamoDB local
    └── local.kafka.conf          # Bootstrap server local
```

---

## 1. Rede Docker

Todos os contêineres compartilham a rede `vpc_dm`. Crie-a antes do primeiro deploy:

```bash
docker network create vpc_dm
```

---

## 2. Infraestrutura Local

O arquivo `local_services.yml` sobe os serviços que replicam AWS MSK e DynamoDB.

### Serviços

| Serviço | Imagem | Porta(s) | Descrição |
|---------|--------|----------|-----------|
| `zookeeper` | `confluentinc/cp-zookeeper:7.6.0` | `22181:2181` | Coordenador do Kafka |
| `kafka-broker-1` | `confluentinc/cp-server:7.6.0` | `29092` (externo), `9092` (interno) | Broker Kafka |
| `schema-registry` | `confluentinc/cp-schema-registry:7.6.0` | `8081` | Registro de schemas Avro |
| `control-center` | `confluentinc/cp-enterprise-control-center:7.6.0` | `9021` | UI de monitoramento Kafka |
| `dynamodb-local` | `amazon/dynamodb-local:2.4.0` | `8000` | DynamoDB local (persistência em volume) |
| `dynamodb-init` | `amazon/aws-cli:2.15.0` | — | One-shot: cria as 3 tabelas DynamoDB na primeira vez |

### Tabelas criadas pelo `dynamodb-init`

| Tabela | Chave primária | Chave de ordenação | Descrição |
|--------|---------------|-------------------|-----------|
| `dm-api-key-semaphore` | `api_key_name` (S) | — | Controla qual processo detém qual chave de API |
| `dm-api-key-consumption` | `api_key_name` (S) | `date` (S) | Contagem diária de chamadas por chave |
| `dm-popular-contracts` | `contract_address` (S) | — | Cache dos contratos mais transacionados |

### Deploy

```bash
# Sobe Kafka + DynamoDB local de uma vez
make deploy_dev_infra

# Ou individualmente:
make deploy_dev_fast       # apenas Kafka
make deploy_dev_dynamodb   # apenas DynamoDB

# Parar
make stop_dev_infra
```

### Conf files

**`conf/local.kafka.conf`**
```ini
NETWORK=mainnet
KAFKA_BROKERS=kafka-broker-1:9092
SCHEMA_REGISTRY_URL=http://schema-registry:8081
```

**`conf/dev.dynamodb.conf`**
```ini
DYNAMODB_ENDPOINT_URL=http://dynamodb-local:8000
AWS_ACCESS_KEY_ID=local
AWS_SECRET_ACCESS_KEY=local
AWS_DEFAULT_REGION=us-east-1
DYNAMODB_SEMAPHORE_TABLE=dm-api-key-semaphore
DYNAMODB_CONSUMPTION_TABLE=dm-api-key-consumption
DYNAMODB_POPULAR_CONTRACTS_TABLE=dm-popular-contracts
APP_ENV=dev
```

---

## 3. Aplicações Python (Captura On-Chain)

O arquivo `python_streaming_apps_layer.yml` sobe as 4 aplicações Python de captura de dados da blockchain, conectadas ao Kafka local e ao DynamoDB local.

### Deploy

```bash
# Sobe as aplicações (com build)
make deploy_dev_stream

# Parar
make stop_dev_stream
```

### Verificar status

```bash
docker compose -f services/compose/python_streaming_apps_layer.yml ps
docker compose -f services/compose/python_streaming_apps_layer.yml logs -f <serviço>
```

Consulte [data_capture.md](../application/data_capture.md) para detalhes das aplicações.

---

## 4. Tópicos Kafka

Antes de iniciar as aplicações, os tópicos devem existir no broker local. Use o script de manutenção disponível no container `onchain-batch-txs`:

```bash
# Criar tópicos (com base em conf/topics_dev.ini)
docker compose -f services/compose/python_streaming_apps_layer.yml run --rm onchain-batch-txs \
  python /app/kafka_maintenance/0_create_topics.py
```

Os tópicos utilizados são:

| Tópico | Produtores | Consumidores |
|--------|-----------|-------------|
| `mainnet.0.application.logs` | Todos os apps (logs) | DLT Silver Logs |
| `mainnet.1.mined_blocks.events` | `mined_blocks_watcher` | `block_data_crawler`, DLT |
| `mainnet.2.blocks.data` | `block_data_crawler` | DLT Bronze, Silver Blocks |
| `mainnet.3.block.txs.hash_id` | `block_data_crawler` | `mined_txs_crawler` |
| `mainnet.4.transactions.data` | `mined_txs_crawler` | DLT Bronze, Silver Txs |

---

## 5. DABs — Databricks Asset Bundles (DEV)

Para testar o processamento de dados, use o **Databricks Free Edition** com os DABs.

### Configuração do target `dev`

Edite `dabs/databricks.yml` e configure a variável do workspace DEV:

```yaml
variables:
  dev_workspace_host:
    default: "https://seu-workspace.azuredatabricks.net"
```

Na prática, o target `dev` usa:
- `catalog: dd_chain_explorer_dev`
- `kafka_bootstrap_servers: localhost:9092` (Kafka local)
- Tabelas DynamoDB apontando para `dm-api-key-*` (pode usar local ou DEV AWS)

### Comandos principais

```bash
# Validar o bundle (não requer workspace)
make dabs_validate

# Fazer deploy em DEV
make dabs_deploy_dev

# Executar um workflow específico em DEV
make dabs_run_dev JOB=dm-ddl-setup            # Setup inicial (cria tabelas)
make dabs_run_dev JOB=dm-periodic-processing  # Processamento periódico
make dabs_run_dev JOB=dm-iceberg-maintenance  # Manutenção de tabelas
make dabs_run_dev JOB=dm-teardown             # Teardown (CUIDADO: apaga tudo)

# Ver status dos recursos deployados em DEV
make dabs_status_dev
```

---

## 6. Terraform (Desenvolvimento)

Para trabalhar com o Terraform localmente:

```bash
# Inicializar todos os módulos
make tf_init_all

# Plan / Apply por módulo
make tf_plan_vpc   && make tf_apply_vpc
make tf_plan_msk   && make tf_apply_msk
```

> **Atenção:** Os módulos usam backend S3 (`dm-chain-explorer-terraform-state`). Para trabalhar no módulo `0_remote_state` (que cria o próprio bucket), faça `terraform init` localmente com backend local primeiro.

---

## 7. Acesso às UIs

| Interface | URL local | Credenciais |
|-----------|-----------|-------------|
| Confluent Control Center | [http://localhost:9021](http://localhost:9021) | sem autenticação |
| Schema Registry API | [http://localhost:8081](http://localhost:8081) | sem autenticação |
| DynamoDB Admin (opcional) | [http://localhost:8000](http://localhost:8000) | sem autenticação |

---

## 8. Limpeza do Ambiente

```bash
# Parar tudo
make stop_dev_infra
make stop_dev_stream

# Remover volumes (dados DynamoDB e Kafka)
docker compose -f services/compose/local_services.yml down -v
```
