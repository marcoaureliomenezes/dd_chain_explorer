# Databricks notebook source
# MAGIC %md
# MAGIC # Reconcile Orphan Blocks — Backfill de Blocos Canônicos Ausentes
# MAGIC
# MAGIC **Escopo:** Detecta blocos orphan sem contrapartida canônica na Bronze e faz o
# MAGIC backfill das transações canônicas via chamadas RPC diretas ao nó Ethereum.
# MAGIC
# MAGIC **Quando usar:** Executar periodicamente (ex.: diário) para corrigir lacunas
# MAGIC geradas quando o Job 2 (`OrphanBlocksProcessor`) falha em re-enqueue o bloco
# MAGIC canônico (race condition ou TTL expirado no cache DynamoDB).
# MAGIC
# MAGIC **Dependências:**
# MAGIC - `s_apps.canonical_blocks_index` — gerado pelo DLT pipeline (TODO-OB-01)
# MAGIC - `eth_mined_blocks` (Bronze) — destino do backfill de blocos
# MAGIC - `eth_transactions` (Bronze) — destino do backfill de transações
# MAGIC - Variável de bundle `{{var.ethereum_rpc_url}}` — endpoint JSON-RPC do nó Ethereum
# MAGIC
# MAGIC **Segurança:** A URL do RPC é lida do spark conf injetado pelo DABs bundle.
# MAGIC Nunca hardcode endpoints ou API keys neste notebook.

# COMMAND ----------

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pyspark.sql import Row, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Configuração

# COMMAND ----------

CATALOG          = spark.conf.get("catalog", "dev")
INGESTION_BUCKET = spark.conf.get("ingestion.s3.bucket", "dm-chain-explorer-dev-ingestion")
# URL do nó Ethereum JSON-RPC injetada pelo bundle como spark conf
# Configurada em databricks.yml: spark_conf: { ethereum.rpc.url: "{{var.ethereum_rpc_url}}" }
ETH_RPC_URL      = spark.conf.get("ethereum.rpc.url", "")

# Número máximo de blocos a reconciliar por execução (evitar timeouts)
MAX_BLOCKS_PER_RUN = int(spark.conf.get("reconcile.max_blocks_per_run", "50"))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Passo 1 — Detectar orphans sem bloco canônico na Bronze
# MAGIC
# MAGIC Um "gap" existe quando:
# MAGIC - `canonical_blocks_index` tem `chain_status = 'orphan'` para um `block_number`
# MAGIC - O mesmo `block_number` NÃO tem nenhuma entrada com `chain_status = 'canonical'`
# MAGIC - O bloco está fora da janela de finalização (block_number < max - 64)
# MAGIC
# MAGIC Isso significa que o bloco canônico nunca foi capturado pelo pipeline de streaming.

# COMMAND ----------

gaps_df = spark.sql(f"""
    WITH orphan_blocks AS (
        SELECT block_number, block_hash AS orphan_hash
        FROM {CATALOG}.s_apps.eth_canonical_blocks_index
        WHERE chain_status = 'orphan'
    ),
    canonical_blocks AS (
        SELECT block_number
        FROM {CATALOG}.s_apps.eth_canonical_blocks_index
        WHERE chain_status = 'canonical'
    ),
    max_confirmed AS (
        SELECT MAX(block_number) - 64 AS threshold
        FROM {CATALOG}.s_apps.eth_canonical_blocks_index
    )
    SELECT
        o.block_number,
        o.orphan_hash,
        current_timestamp() AS detected_at
    FROM orphan_blocks o
    LEFT JOIN canonical_blocks c ON o.block_number = c.block_number
    CROSS JOIN max_confirmed m
    WHERE c.block_number IS NULL                  -- sem canônico na Bronze
      AND o.block_number < m.threshold            -- fora da janela unconfirmed
    ORDER BY o.block_number DESC
    LIMIT {MAX_BLOCKS_PER_RUN}
""")

gap_count = gaps_df.count()
print(f"Gaps detectados (orphans sem canônico): {gap_count}")
gaps_df.show(truncate=False)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Passo 2 — Buscar blocos canônicos via RPC
# MAGIC
# MAGIC Para cada gap, chama `eth_getBlockByNumber` no nó Ethereum para obter
# MAGIC o bloco canônico real (aquele que a rede escolheu para aquele número).

# COMMAND ----------

def _rpc_call(url: str, method: str, params: list) -> Any:
    """Executa uma chamada JSON-RPC via requests. Levanta RuntimeError em caso de erro."""
    import requests  # disponível no Databricks Runtime

    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error {method}: {data['error']}")
    return data.get("result")


def fetch_canonical_block(block_number: int, rpc_url: str) -> Optional[dict]:
    """
    Busca o bloco canônico pelo número via eth_getBlockByNumber.
    Retorna o dict do bloco com transações completas, ou None se não encontrado.
    """
    hex_number = hex(block_number)
    result = _rpc_call(rpc_url, "eth_getBlockByNumber", [hex_number, True])
    return result


# COMMAND ----------
# MAGIC %md
# MAGIC ## Passo 3 — Backfill na Bronze
# MAGIC
# MAGIC Escreve o bloco canônico recuperado em `eth_mined_blocks` e suas transações
# MAGIC em `eth_transactions`, usando `MERGE` para evitar duplicatas (idempotente).

# COMMAND ----------

def _hex_to_int(value: Any) -> Optional[int]:
    """Converte valor hex string para int. Retorna None se nulo/inválido."""
    if value is None:
        return None
    try:
        return int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value)
    except (ValueError, TypeError):
        return None


def backfill_block(block: dict, catalog: str, ingestion_bucket: str) -> dict:
    """
    Insere o bloco canônico e suas transações na Bronze via Delta MERGE.
    Retorna um resumo com block_number, block_hash, tx_count, status.
    """
    block_number = _hex_to_int(block.get("number"))
    block_hash   = block.get("hash")
    transactions = block.get("transactions", [])
    ingested_at  = datetime.now(timezone.utc)

    # ── Bloco → eth_mined_blocks ────────────────────────────────────────────
    block_row = {
        "number":           block_number,
        "hash":             block_hash,
        "parentHash":       block.get("parentHash"),
        "timestamp":        _hex_to_int(block.get("timestamp")),
        "miner":            block.get("miner"),
        "difficulty":       block.get("difficulty"),
        "totalDifficulty":  block.get("totalDifficulty"),
        "nonce":            block.get("nonce"),
        "size":             _hex_to_int(block.get("size")),
        "baseFeePerGas":    block.get("baseFeePerGas"),
        "gasLimit":         _hex_to_int(block.get("gasLimit")),
        "gasUsed":          _hex_to_int(block.get("gasUsed")),
        "logsBloom":        block.get("logsBloom"),
        "extraData":        block.get("extraData"),
        "transactionsRoot": block.get("transactionsRoot"),
        "stateRoot":        block.get("stateRoot"),
        "transactions":     [t.get("hash") for t in transactions],
        "withdrawals":      block.get("withdrawals"),
        "_ingested_at":     ingested_at,
        "dat_ref":          ingested_at.date(),
        "_reconciled":      True,
    }

    block_df = spark.createDataFrame([Row(**block_row)])

    # MERGE idempotente: insere somente se o hash ainda não existe
    block_df.createOrReplaceTempView("_reconcile_block_stage")
    spark.sql(f"""
        MERGE INTO {catalog}.b_ethereum.eth_mined_blocks AS target
        USING _reconcile_block_stage AS source
        ON target.hash = source.hash
        WHEN NOT MATCHED THEN INSERT *
    """)

    # ── Transações → eth_transactions ──────────────────────────────────────
    if transactions:
        tx_rows = []
        for tx in transactions:
            tx_data = {
                "hash":             tx.get("hash"),
                "blockNumber":      block_number,
                "blockHash":        block_hash,
                "transactionIndex": _hex_to_int(tx.get("transactionIndex")),
                "from":             tx.get("from"),   # reserved keyword — dict key only
                "to":               tx.get("to"),
                "value":            tx.get("value"),
                "input":            tx.get("input"),
                "gas":              tx.get("gas"),
                "gasPrice":         tx.get("gasPrice"),
                "nonce":            _hex_to_int(tx.get("nonce")),
                "v":                tx.get("v"),
                "r":                tx.get("r"),
                "s":                tx.get("s"),
                "type":             tx.get("type"),
                "accessList":       json.dumps(tx.get("accessList", [])),
                "_ingested_at":     ingested_at,
                "dat_ref":          ingested_at.date(),
                "_reconciled":      True,
            }
            tx_rows.append(Row(**tx_data))

        tx_df = spark.createDataFrame(tx_rows)
        tx_df.createOrReplaceTempView("_reconcile_tx_stage")
        spark.sql(f"""
            MERGE INTO {catalog}.b_ethereum.eth_transactions AS target
            USING _reconcile_tx_stage AS source
            ON target.hash = source.hash
            WHEN NOT MATCHED THEN INSERT *
        """)

    return {
        "block_number": block_number,
        "block_hash":   block_hash,
        "tx_count":     len(transactions),
        "status":       "backfilled",
    }


# COMMAND ----------
# MAGIC %md
# MAGIC ## Passo 4 — Executar backfill para todos os gaps detectados

# COMMAND ----------

if not ETH_RPC_URL:
    print("⚠️  ethereum.rpc.url não configurado. Abortando reconciliação.")
    dbutils.notebook.exit(json.dumps({"status": "skipped", "reason": "no_rpc_url"}))

results = []
errors  = []

for row in gaps_df.collect():
    block_number = row["block_number"]
    orphan_hash  = row["orphan_hash"]
    try:
        block = fetch_canonical_block(block_number, ETH_RPC_URL)
        if block is None:
            errors.append({"block_number": block_number, "error": "block_not_found"})
            continue

        canonical_hash = block.get("hash")
        if canonical_hash == orphan_hash:
            # RPC retornou o mesmo hash — ainda é orphan do ponto de vista da rede
            errors.append({"block_number": block_number, "error": "rpc_returned_orphan_hash"})
            continue

        summary = backfill_block(block, CATALOG, INGESTION_BUCKET)
        results.append(summary)
        print(f"✅  Bloco {block_number}: canônico {canonical_hash[:12]}... | {summary['tx_count']} txs")

    except Exception as exc:
        errors.append({"block_number": block_number, "error": str(exc)})
        print(f"❌  Bloco {block_number}: {exc}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Passo 5 — Resumo da execução

# COMMAND ----------

summary = {
    "gaps_detected":   gap_count,
    "blocks_backfilled": len(results),
    "errors":          len(errors),
    "details":         results,
    "error_details":   errors,
}

print(json.dumps(summary, indent=2, default=str))

if errors:
    print(f"\n⚠️  {len(errors)} blocos com erro — verificar logs acima para detalhes.")

dbutils.notebook.exit(json.dumps(summary, default=str))
