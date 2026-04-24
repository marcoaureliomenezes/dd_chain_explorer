# apps/lambda — Funções Lambda

Funções AWS Lambda do projeto `dd-chain-explorer`. Cada subfolder é uma função independente com seu próprio `handler.py` e `requirements.txt`.

---

## Funções

### `contracts_ingestion/`

**Trigger**: EventBridge Scheduler — execução horária.

**Fluxo**: EventBridge → Lambda → Etherscan API → S3 `raw/batch/`

Busca transações de contratos populares na API Etherscan e salva os resultados como JSON no bucket S3 de ingestão. Os dados são consumidos posteriormente por workflows Databricks (Bronze → Silver via `workflow_batch_contracts`).

| Variável de ambiente | Descrição |
|----------------------|-----------|
| `S3_BUCKET` | Bucket S3 de ingestão raw |
| `S3_PREFIX` | Prefixo de destino (`batch/`) |
| `SSM_ETHERSCAN_PATH` | Path SSM com API keys Etherscan |
| `DYNAMODB_TABLE` | Tabela DynamoDB single-table |

---

### `gold_to_dynamodb/`

**Trigger**: S3 Event — `s3:ObjectCreated:*` no prefixo `exports/gold_api_keys/`.

**Fluxo**: S3 PutObject → Lambda → DynamoDB (entidade `CONSUMPTION`)

Lê arquivos JSON exportados pelas views Gold do Databricks e sincroniza os dados de consumo de API keys para a tabela DynamoDB, permitindo que os jobs de streaming consultem o histórico de uso em tempo real.

| Variável de ambiente | Descrição |
|----------------------|-----------|
| `DYNAMODB_TABLE` | Tabela DynamoDB single-table |

---

## Deploy

### DEV

Gerenciado por Terraform em `services/dev/02_lambda/`.

```bash
make tf_apply_dev_lambda    # terraform apply em 02_lambda
make tf_destroy_dev_lambda  # terraform destroy em 02_lambda
```

### PROD

Gerenciado por Terraform em `services/prd/06_lambda/`.  
Deploy via CI/CD: `.github/workflows/deploy_all_dm_applications.yml` (Lambda functions).

```
build-artifacts → lambda-hml-test → lambda-prod-deploy (terraform apply)
```

### Build local de artifacts

```bash
# Layer com dm_chain_utils
pip install utils/ -t /tmp/layer/python
zip -r layer.zip /tmp/layer/

# Handler contracts_ingestion
zip contracts_ingestion.zip apps/lambda/contracts_ingestion/handler.py

# Handler gold_to_dynamodb
zip gold_to_dynamodb.zip apps/lambda/gold_to_dynamodb/handler.py
```

---

## Estrutura

```
apps/lambda/
  contracts_ingestion/
    handler.py         # Lambda handler
    requirements.txt   # Dependências (dm-chain-utils, boto3)
  gold_to_dynamodb/
    handler.py         # Lambda handler
```


