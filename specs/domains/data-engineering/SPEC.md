# Spec: Domínio — Data Engineering

> **Status:** Implementado
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/architecture.md`, `specs/memory/data-catalog.md`, `specs/memory/tech-stack.md`

---

## Escopo

Toda a camada analítica Databricks de processamento de dados:
- **2 pipelines DLT** (`apps/dabs/dlt_ethereum/`, `apps/dabs/dlt_app_logs/`)
- **Batch jobs** de orquestração e manutenção (`apps/dabs/job_*/`)
- **Modelo de dados Medallion** — schemas Bronze, Silver, Gold

Este domínio NÃO inclui: dashboards, Genie Spaces, alerts (→ `data-analytics`), infraestrutura Terraform, streaming apps.

---

## Arquitetura Medallion

```
S3 Bronze (NDJSON via Firehose)
  └── Auto Loader (cloudFiles)
        ├── Pipeline dm-ethereum
        │     Bronze (b_ethereum) → Silver (s_apps) → Gold (g_apps, g_network)
        └── Pipeline dm-app-logs
              Bronze (b_app_logs) → Silver (s_logs) → Gold (g_api_keys)
```

**Invariante crítica:** nunca use `path=` em `@dlt.table` — Unity Catalog proíbe paths explícitos.

---

## Pipelines DLT

### `dlt_ethereum` — Pipeline Principal

**Trigger:** `job_trigger_all` a cada 5 minutos com `availableNow: true`.

| Camada | Schema | Tabelas/MVs |
|--------|--------|-------------|
| Bronze | `b_ethereum` | `eth_mined_blocks`, `eth_transactions`, `eth_txs_input_decoded`, `popular_contracts_txs` |
| Silver | `s_apps` | `eth_blocks`, `eth_blocks_withdrawals`, `eth_transactions_staging`, `txs_inputs_decoded_fast`, `transactions_ethereum`, `eth_canonical_blocks_index` (MV) |
| Gold | `g_apps` | `popular_contracts_ranking`, `peer_to_peer_txs`, `gas_price_distribution_hourly`, `ethereum_gas_consume`, `transactions_lambda` (union streaming + batch) |
| Gold | `g_network` | `network_metrics_hourly`, `block_production_rate`, `tps_hourly` (e outras MVs de rede) |

### `dlt_app_logs` — Pipeline de Logs

**Trigger:** `job_trigger_all` após conclusão de `dm-ethereum` (offset 2 min).

| Camada | Schema | Tabelas/MVs |
|--------|--------|-------------|
| Bronze | `b_app_logs` | `b_app_logs_data` (CloudWatch double-gzip via binaryFile Auto Loader) |
| Silver | `s_logs` | `logs_streaming`, `logs_batch` |
| Gold | `g_api_keys` | `etherscan_consumption`, `web3_keys_consumption` |

---

## Batch Jobs

| Componente | Schedule | Propósito |
|------------|----------|-----------|
| `job_trigger_all` | A cada 5 min | Dispara `dm-ethereum` → `dm-app-logs` sequencialmente |
| `job_ddl_setup` | Manual / on-deploy | Cria schemas, tabelas externas e views no Unity Catalog |
| `job_delta_maintenance` | A cada 12h | OPTIMIZE + VACUUM em todas as tabelas Delta |
| `job_export_gold` | A cada 1h | Exporta MVs Gold para S3 JSON (input para `gold_to_dynamodb` Lambda) |
| `job_reconcile_orphans` | Manual (P0: unpaused) | Reconcilia blocos sem entrada em `eth_canonical_blocks_index` |
| `job_full_refresh` | Manual | Full refresh: drop + recria todas as tabelas DLT |

---

## Requisitos Funcionais

### DLT

**FR-DE-001 — Sem `path=` em decorators**
`@dlt.table` e `@dlt.view` nunca devem usar o parâmetro `path=`. Unity Catalog gerencia o storage location automaticamente.

**FR-DE-002 — Auto Loader com schemaLocation**
Todo Auto Loader deve declarar `cloudFiles.schemaLocation` para evitar inferência de schema a cada restart.

**FR-DE-003 — Validações com expect_or_drop**
Registros com campos obrigatórios nulos (tx_hash, block_number, from_address) devem ser descartados via `@dlt.expect_or_drop` — nunca falhar o pipeline por dados inválidos.

**FR-DE-004 — Canonical blocks index**
`s_apps.eth_canonical_blocks_index` deve classificar todo bloco como `canonical` ou `orphan` via cadeia de parent_hash. Esta MV é pré-requisito de todas as MVs Gold que dependem de dados canônicos.

**FR-DE-005 — transactions_lambda union**
`g_apps.transactions_lambda` deve unir `transactions_ethereum` (streaming) com `popular_contracts_txs` (batch), deduplicando por `tx_hash` com prioridade para o registro com melhor qualidade de decode (`decode_type`).

### Batch

**FR-DE-010 — Trigger sequencial**
`job_trigger_all` deve sempre iniciar `dm-ethereum` e aguardar sua conclusão antes de iniciar `dm-app-logs`. Nunca disparar em paralelo.

**FR-DE-011 — DDL idempotente**
`job_ddl_setup` deve usar `CREATE SCHEMA IF NOT EXISTS` e `CREATE TABLE IF NOT EXISTS` em todos os DDL statements. Nunca `DROP + CREATE`.

**FR-DE-012 — Export Gold particionado**
`job_export_gold` deve exportar arquivos JSON com partição de data para que `gold_to_dynamodb` Lambda processe incrementalmente.

**FR-DE-013 — Scaffold via beteugeuse**
Todo novo componente DABs (pipeline DLT ou job batch) deve ser criado via `beteugeuse dlt create` ou `beteugeuse job create` — nunca manualmente do zero.

---

## Padrões de Código (spark_python_task)

```python
# Template obrigatório para scripts .py em batch jobs
import argparse, logging
from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

class MyProcessor:
    def __init__(self, spark: SparkSession, catalog: str, env: str): ...
    def run(self) -> None: ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--env", required=True)
    args = parser.parse_args()
    MyProcessor(SparkSession.builder.getOrCreate(), args.catalog, args.env).run()

if __name__ == "__main__": main()
```

Regras: sem `dbutils`, sem `print()`, sem hardcode de catalog, argparse para todos os parâmetros.

---

## Requisitos Não-Funcionais

- **NFR-DE-001:** Catalog sempre via `${var.catalog}` — nunca hardcode.
- **NFR-DE-002:** Auto Loader S3 path: sempre `s3://{bucket}/raw/{stream}/` — `bronze/` é schema DLT, nunca prefixo S3.
- **NFR-DE-003:** Pipeline schedules PAUSED em dev/hml, UNPAUSED apenas em prod.

---

## Fora de Escopo (v1)

- Datalake backfill (histórico pré-plataforma) — feature futura
- Schema evolution automatizada com versionamento explícito
- Streaming DLT (hoje: triggered com `availableNow`)
