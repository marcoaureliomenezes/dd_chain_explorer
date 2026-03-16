# dm-chain-utils

Shared Python utility library for `dd_chain_explorer` Docker applications (`onchain-stream-txs` and `onchain-batch-txs`).

## Modules

| Module | Description |
|---|---|
| `api_keys_manager` | DynamoDB-based API key rotation semaphore |
| `dm_etherscan` | Etherscan API v2 client (ABI cache + 4byte fallback) |
| `dm_kafka_admin` | Kafka topic admin operations |
| `dm_kafka_client` | Confluent Kafka AVRO producer/consumer |
| `dm_logger` | Kafka AVRO logging handler + console handler |
| `dm_parameter_store` | AWS SSM Parameter Store client |
| `dm_dynamodb` | DynamoDB single-table wrapper (PK/SK, TTL, batch ops) |
| `dm_schema_reg_client` | Schema Registry abstraction (DEV: Confluent SR, PROD: AWS Glue) |
| `dm_web3_client` | Web3 Ethereum node handler via SSM API keys |

## Usage

### PROD (installed as package)
```bash
pip install dm-chain-utils
from dm_chain_utils.dm_dynamodb import DMDynamoDB
```

### DEV (volume mount via Docker Compose)
The library is mounted at `/app/dm_chain_utils` via docker-compose volume.
No `pip install` needed in DEV — Python resolves the package from `/app`.

### Building a wheel locally
```bash
cd dd_chain_explorer/utils
pip install build
python -m build --wheel
pip install dist/dm_chain_utils-*.whl
```

## Running tests
```bash
cd dd_chain_explorer/utils
pip install -e ".[dev]"
pytest tests/
```
