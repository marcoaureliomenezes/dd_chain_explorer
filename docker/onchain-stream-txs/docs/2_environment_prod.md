# Ambiente de Producao

Este documento descreve como os jobs de streaming sao executados em producao na AWS, os servicos gerenciados utilizados e as configuracoes especificas de ambiente.

---

## Visao Geral da Infraestrutura

Em producao, os jobs de streaming sao executados como tarefas ECS Fargate. Toda a infraestrutura e provisionada via Terraform, organizada em modulos independentes no diretorio `dd_chain_explorer/terraform/`.

```
                          +------------------------------+
                          |       AWS Cloud (sa-east-1)  |
                          |                              |
  +-------------------+   |   +----------------------+   |   +----------------------+
  | ECR               |   |   | ECS Fargate          |   |   | CloudWatch Logs      |
  | (Imagens Docker)  |------>| Cluster: dm-chain-   |------>| /ecs/dm-chain-       |
  +-------------------+   |   | explorer-ecs         |   |   | explorer             |
                          |   +----------+-----------+   |   +----------------------+
                          |              |               |
                          |   +----------v-----------+   |
                          |   |  VPC Privada         |   |
                          |   |  (Subnets privadas)  |   |
                          |   +----------+-----------+   |
                          |              |               |
              +-----------+--------------+--------------++-----------+
              |                          |                           |
  +-----------v-----------+  +-----------v-----------+  +-----------v-----------+
  | Amazon MSK            |  | AWS Glue Schema       |  | Amazon DynamoDB       |
  | (Apache Kafka 3.x)   |  | Registry              |  | (Single-table)        |
  | 2 brokers, 2 AZs     |  | ChainExplorer-schema- |  | dm-chain-explorer     |
  | TLS + IAM auth        |  | registry              |  | PAY_PER_REQUEST       |
  +--+--------------------+  +-----------+-----------+  +-----------+-----------+
     |                                   |                          |
     +-----------------------------------+--------------------------+
                          |
              +-----------v-----------+
              | AWS SSM Parameter     |
              | Store                 |
              | (API keys cifradas)   |
              +-----------------------+
```

---

## ECS Fargate

Os servicos de streaming sao deployados como ECS Services dentro do cluster `dm-chain-explorer-ecs`. A definicao Terraform esta em `terraform/6_ecs/ecs.tf`.

### Configuracao do cluster

```hcl
resource "aws_ecs_cluster" "dm" {
  name = "dm-chain-explorer-ecs"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
```

O cluster utiliza capacity providers `FARGATE` e `FARGATE_SPOT`.

### Task Definitions

Cada job possui uma Task Definition independente:

| Task Definition | Job | CPU | Memoria | Replicas |
|----------------|-----|-----|---------|----------|
| `dm-mined-blocks-watcher` | Job 1 - Deteccao de blocos | 256 | 512 MB | 1 |
| `dm-orphan-blocks-watcher` | Job 2 - Blocos orfaos | 256 | 512 MB | 1 |
| `dm-block-data-crawler` | Job 3 - Dados de blocos | 512 | 1024 MB | 1 |
| `dm-mined-txs-crawler` | Job 4 - Transacoes brutas | 512 | 1024 MB | 8 |

O Job 4 (`mined-txs-crawler`) e o unico com multiplas replicas, pois precisa paralelizar a captura de transacoes para acompanhar o throughput da rede Ethereum.

### Rede e Seguranca

Todas as tarefas ECS sao executadas em subnets privadas (sem IP publico), acessando os servicos gerenciados (MSK, DynamoDB, SSM) via endpoints internos da VPC:

```hcl
network_configuration {
  subnets          = data.terraform_remote_state.vpc.outputs.private_subnet_ids
  security_groups  = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
  assign_public_ip = false
}
```

### Logging

Os logs de cada container sao enviados ao CloudWatch Logs via driver `awslogs`:

```hcl
logConfiguration = {
  logDriver = "awslogs"
  options = {
    awslogs-group         = "/ecs/dm-chain-explorer"
    awslogs-region        = var.region
    awslogs-stream-prefix = "ecs"
  }
}
```

Alem do CloudWatch, cada job tambem envia logs estruturados para o topico Kafka `mainnet.0.application.logs` via `KafkaLoggingHandler`.

### IAM Roles

Cada Task Definition referencia duas IAM roles (definidas em `terraform/2_iam/`):

- **Execution Role** (`ecs_task_execution_role_arn`): permite ao ECS Agent puxar imagens do ECR e escrever no CloudWatch.
- **Task Role** (`ecs_task_role_arn`): permite que o codigo da aplicacao acesse SSM Parameter Store, MSK via IAM auth e outros servicos AWS.

---

## Amazon MSK (Apache Kafka)

O cluster Kafka gerenciado e provisionado em `terraform/3_msk/msk.tf`.

### Configuracao do cluster

| Parametro | Valor |
|-----------|-------|
| Nome | `dm-chain-explorer-msk` |
| Brokers | 2 (1 por AZ) |
| Autenticacao | IAM (SASL) |
| Criptografia em transito | TLS_PLAINTEXT |
| Criptografia em repouso | KMS dedicada |
| Retencao padrao | 168 horas (7 dias) |
| Particoes padrao | 8 |
| Auto-create topics | Desabilitado |

### Configuracoes do broker

```properties
auto.create.topics.enable=false
default.replication.factor=2
min.insync.replicas=1
num.partitions=8
log.retention.hours=168
```

### Topicos

Os topicos sao criados previamente via script `0_create_topics.py` (no modulo `onchain-batch-txs`). Em producao, a criacao de topicos segue a mesma nomenclatura do ambiente de desenvolvimento:

| Topico | Particoes | Fator de Replicacao |
|--------|-----------|---------------------|
| `mainnet.0.application.logs` | 1 | 2 |
| `mainnet.0.batch.logs` | 1 | 2 |
| `mainnet.1.mined_blocks.events` | 1 | 2 |
| `mainnet.2.blocks.data` | 1 | 2 |
| `mainnet.3.block.txs.hash_id` | 8 | 2 |
| `mainnet.4.transactions.data` | 8 | 2 |
| `mainnet.5.transactions.input_decoded` | 4 | 2 |

O topico `mainnet.3.block.txs.hash_id` possui 8 particoes para permitir paralelismo no consumo pelo Job 4.

---

## AWS Glue Schema Registry

Em producao, o Schema Registry e o AWS Glue Schema Registry em vez do Confluent Schema Registry local. O recurso Terraform esta em `terraform/3_msk/msk.tf`:

```hcl
resource "aws_glue_registry" "dm" {
  registry_name = "dm-chain-explorer-schema-registry"
}
```

O modulo `schema_registry_utils.py` detecta `APP_ENV=prod` e automaticamente busca schemas no Glue:

```python
def _glue_get_schema(schema_name, registry_name="ChainExplorer-schema-registry"):
    client = boto3.client("glue", region_name="sa-east-1")
    response = client.get_schema_version(
        SchemaId={"SchemaName": schema_name, "RegistryName": registry_name},
        SchemaVersionNumber={"LatestVersion": True},
    )
    return response["SchemaDefinition"]
```

---

## Amazon DynamoDB

O DynamoDB e utilizado como store de estado compartilhado, substituindo o Redis. A tabela segue o padrao single-table design.

### Configuracao

| Parametro | Valor |
|-----------|-------|
| Tabela | `dm-chain-explorer` |
| Partition Key | `pk` (String) |
| Sort Key | `sk` (String) |
| Billing | PAY_PER_REQUEST (on-demand) |
| TTL | Atributo `ttl` (expiracao automatica) |
| PITR | Habilitado (point-in-time recovery) |
| SSE | Habilitado (criptografia em repouso) |

O design single-table utiliza PK/SK para modelar diferentes entidades (SEMAPHORE, COUNTER, BLOCK_CACHE, ABI, ABI_NEG, CONTRACT, CONSUMPTION) numa unica tabela.

### Acesso via DMDynamoDB

O wrapper `dm_dynamodb.py` usa `boto3` e detecta automaticamente as credenciais AWS:
- DEV: usa `~/.aws/credentials` montado no container
- PROD: usa IAM Task Role do ECS (sem credenciais explicitas)

---

## AWS SSM Parameter Store

As API keys dos provedores Web3 (Alchemy, Infura) e Etherscan sao armazenadas como parametros `SecureString` no SSM Parameter Store (regiao `sa-east-1`).

### Hierarquia

```
/web3-api-keys/
  alchemy/api-key-1 .. api-key-4
  infura/api-key-1  .. api-key-17
/etherscan-api-keys/
  api-key-1 .. api-key-5
```

Em producao, as tarefas ECS acessam o SSM via IAM role (sem credenciais explicitas). O `ParameterStoreClient` usa `boto3` que automaticamente assume a role da task.

---

## Variaveis de Ambiente em Producao

As variaveis de ambiente sao definidas diretamente nas Task Definitions do ECS (via Terraform). As principais diferencas em relacao ao ambiente de desenvolvimento:

| Variavel | DEV | PROD |
|----------|-----|------|
| `KAFKA_BROKERS` | `kafka-broker-1:9092` | Endpoint MSK (bootstrap servers IAM) |
| `SCHEMA_REGISTRY_URL` | `http://schema-registry:8081` | Nao utilizado (`APP_ENV=prod` usa Glue) |
| `APP_ENV` | `dev` | `prod` |
| `DYNAMODB_TABLE` | `dm-chain-explorer` | `dm-chain-explorer` |
| Credenciais AWS | `~/.aws` montado | IAM Task Role |

---

## Referencias Terraform

| Modulo | Diretorio | Recurso principal |
|--------|-----------|-------------------|
| Remote State | `terraform/0_remote_state/` | S3 backend para state files |
| VPC | `terraform/1_vpc/` | VPC, subnets, security groups |
| IAM | `terraform/2_iam/` | Roles para ECS tasks |
| MSK | `terraform/3_msk/` | Cluster Kafka + Glue Schema Registry |
| S3 | `terraform/4_s3/` | Buckets de armazenamento |
| DynamoDB | `terraform/5_dynamodb/` | Tabelas auxiliares |
| ECS | `terraform/6_ecs/` | Cluster, task definitions, services |
| Databricks | `terraform/7_databricks/` | Workspace Databricks (lakehouse) |
| DynamoDB | `terraform/9_dynamodb/` | Tabela DynamoDB single-table |
| Lambda | `terraform/10_lambda/` | Lambda gold_to_dynamodb (S3→DynamoDB) |