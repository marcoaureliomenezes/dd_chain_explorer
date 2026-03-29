"""setup_ddl.py — DDL completo para DD Chain Explorer Unity Catalog.

Cria todos os schemas, tabelas EXTERNAL DDL-gerenciadas, aplica comentários
em todas as colunas das tabelas DLT-gerenciadas e configura RLS.

Modos de execução:
  1. Spark (HML/PRD): usa spark.sql() — executado via workflow dm-ddl-setup.
  2. Warehouse (DEV Free Edition): usa Databricks Statements REST API.
     Requer --warehouse-id e autenticação via DATABRICKS_HOST + DATABRICKS_TOKEN
     (ou databricks profile ativo via CLI).

Flags:
  --catalog               Catálogo Unity Catalog (obrigatório)
  --lakehouse-s3-bucket   Bucket S3 para tabelas EXTERNAL (obrigatório)
  --admin-group           Grupo de administradores para RLS (default: admins)
  --drop                  DROP SCHEMA CASCADE em todos os schemas antes de criar
  --comments-only         Aplica somente comentários (sem CREATE/DROP)
  --warehouse-id          SQL Warehouse ID (modo DEV/Free Edition)
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Optional

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Executor: abstrai spark.sql() vs Databricks Statements REST API
# ---------------------------------------------------------------------------

class _SparkExecutor:
    def __init__(self, spark) -> None:
        self._spark = spark

    def sql(self, statement: str) -> None:
        self._spark.sql(statement)


class _WarehouseExecutor:
    """Executa SQL via Databricks Statements API (sem Spark)."""

    def __init__(self, host: str, token: str, warehouse_id: str) -> None:
        import urllib.request
        import urllib.error
        self._host = host.rstrip("/")
        self._token = token
        self._warehouse_id = warehouse_id
        self._urllib_request = urllib.request
        self._urllib_error = urllib.error

    def sql(self, statement: str) -> None:
        import json
        url = f"{self._host}/api/2.0/sql/statements/"
        payload = json.dumps({
            "warehouse_id": self._warehouse_id,
            "statement": statement,
            "wait_timeout": "50s",
            "on_wait_timeout": "CANCEL",
        }).encode()
        req = self._urllib_request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._urllib_request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
        except self._urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from Statements API: {body}") from exc

        state = result.get("status", {}).get("state", "UNKNOWN")
        if state == "RUNNING":
            # Poll for completion
            stmt_id = result["statement_id"]
            self._wait(stmt_id)
        elif state not in ("SUCCEEDED",):
            err = result.get("status", {}).get("error", {})
            raise RuntimeError(f"Statement failed ({state}): {err.get('message', result)}")

    def _wait(self, statement_id: str) -> None:
        import json
        url = f"{self._host}/api/2.0/sql/statements/{statement_id}"
        req = self._urllib_request.Request(
            url,
            headers={"Authorization": f"Bearer {self._token}"},
            method="GET",
        )
        for _ in range(60):
            time.sleep(3)
            with self._urllib_request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            state = result.get("status", {}).get("state", "UNKNOWN")
            if state == "SUCCEEDED":
                return
            if state not in ("RUNNING", "PENDING"):
                err = result.get("status", {}).get("error", {})
                raise RuntimeError(f"Statement failed ({state}): {err.get('message', result)}")
        raise TimeoutError(f"Statement {statement_id} still running after 3 min")


def _build_warehouse_executor(warehouse_id: str, host: Optional[str]) -> _WarehouseExecutor:
    """Resolve host + token from (in priority order):
    1. --host CLI arg + DATABRICKS_TOKEN env var
    2. DATABRICKS_HOST + DATABRICKS_TOKEN env vars
    3. ~/.databrickscfg [DEFAULT] profile
    """
    actual_host = host or os.environ.get("DATABRICKS_HOST", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")

    if not actual_host or not token:
        # Read ~/.databrickscfg
        import configparser
        cfg_path = os.path.expanduser("~/.databrickscfg")
        if os.path.exists(cfg_path):
            config = configparser.ConfigParser()
            config.read(cfg_path)
            profile = "DEFAULT"
            if not actual_host:
                raw_host = config.get(profile, "host", fallback="")
                # Strip query string (e.g. ?o=...) that Databricks may append
                actual_host = raw_host.split("?")[0].rstrip("/")
            if not token:
                token = config.get(profile, "token", fallback="")

    if not actual_host or not token:
        raise RuntimeError(
            "Cannot determine Databricks host/token. "
            "Set DATABRICKS_HOST + DATABRICKS_TOKEN env vars, "
            "pass --host, or configure ~/.databrickscfg [DEFAULT] profile."
        )
    return _WarehouseExecutor(actual_host, token, warehouse_id)


# ---------------------------------------------------------------------------
# Main DDL class
# ---------------------------------------------------------------------------

class DDChainExplorerDDL:
    """
    DDL completo para DD Chain Explorer Unity Catalog.

    Tabelas EXTERNAL (DDL-gerenciadas):
      - b_ethereum.popular_contracts_txs
      - s_apps.transactions_batch

    Tabelas DLT-gerenciadas (comentários aplicados via ALTER TABLE):
      Bronze b_ethereum:  b_blocks_data, b_transactions_data, b_transactions_decoded
      Bronze b_app_logs:  b_app_logs_data, logs_streaming, logs_batch
      Silver s_apps:      blocks_fast, transactions_fast, txs_inputs_decoded_fast,
                          transactions_ethereum, blocks_withdrawals
      Gold s_apps:        popular_contracts_ranking, peer_to_peer_txs,
                          ethereum_gas_consume, transactions_lambda
      Gold g_network:     network_metrics_hourly
      Gold g_api_keys:    etherscan_consumption, web3_keys_consumption
    """

    # Schemas gerenciados por este script
    ALL_SCHEMAS = (
        "b_ethereum",
        "b_app_logs",
        "s_apps",
        "s_logs",
        "g_network",
        "g_api_keys",
    )

    def __init__(self, executor, catalog: str, lakehouse_bucket: str) -> None:
        self._exec = executor
        self.catalog = catalog
        self.lakehouse_bucket = lakehouse_bucket

    def _sql(self, statement: str) -> None:
        _log.debug("SQL: %s", statement[:120].replace("\n", " "))
        self._exec.sql(statement)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def drop_all(self) -> None:
        """DROP SCHEMA CASCADE em todos os schemas — destrói todas as tabelas."""
        cat = self.catalog
        for schema in self.ALL_SCHEMAS:
            self._sql(f"DROP SCHEMA IF EXISTS `{cat}`.{schema} CASCADE")
            _log.info("Dropped schema: %s.%s", cat, schema)

    def setup_all(self, admin_group: str = "admins") -> None:
        """Criação completa: schemas + tabelas EXTERNAL + RLS."""
        self._create_schemas()
        self._create_bronze_tables()
        self._create_silver_tables()
        self._apply_rls(admin_group)
        _log.info("DDL setup complete for catalog '%s'", self.catalog)

    def apply_comments(self) -> None:
        """Aplica comentários em todas as tabelas DLT-gerenciadas."""
        self._apply_dlt_table_comments()
        _log.info("Column comments applied for catalog '%s'", self.catalog)

    # ------------------------------------------------------------------
    # Schemas
    # ------------------------------------------------------------------

    def _create_schemas(self) -> None:
        cat = self.catalog
        for schema in self.ALL_SCHEMAS:
            self._sql(f"CREATE SCHEMA IF NOT EXISTS `{cat}`.{schema}")
            _log.info("Schema ensured: %s.%s", cat, schema)

    # ------------------------------------------------------------------
    # Bronze EXTERNAL tables (DDL-gerenciadas — não gerenciadas por DLT)
    # ------------------------------------------------------------------

    def _create_bronze_tables(self) -> None:
        cat = self.catalog
        bucket = self.lakehouse_bucket
        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.popular_contracts_txs (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente na rede Ethereum (0x...)',
            tx_hash           STRING    COMMENT 'Hash único da transação Ethereum (0x...)',
            block_number      BIGINT    COMMENT 'Número do bloco que contém a transação',
            timestamp         TIMESTAMP COMMENT 'Timestamp da transação conforme reportado pela API Etherscan',
            from_address      STRING    COMMENT 'Endereço EOA (Externally Owned Account) que originou a transação',
            to_address        STRING    COMMENT 'Endereço de destino — contrato ou EOA receptor',
            value             STRING    COMMENT 'Valor transferido em Wei representado como string para evitar overflow de 256 bits',
            gas_used          BIGINT    COMMENT 'Gas efetivamente consumido pela transação (receipt.gasUsed)',
            input             STRING    COMMENT 'Payload codificado em hexadecimal enviado ao contrato (seletor 4 bytes + parâmetros ABI-encoded)',
            ingestion_date    DATE      COMMENT 'Data de execução do job de ingestão batch — usada como chave de partição Delta'
          )
          COMMENT 'Bronze EXTERNAL: transações de contratos populares ingeridas via job batch da API Etherscan (hourly). Particionado por data de ingestão.'
          USING DELTA
          PARTITIONED BY (ingestion_date)
          LOCATION 's3://{bucket}/b_ethereum/popular_contracts_txs'
          TBLPROPERTIES ('quality' = 'bronze')
        """)
        _log.info("Table ensured: %s.b_ethereum.popular_contracts_txs", cat)

    # ------------------------------------------------------------------
    # Silver EXTERNAL tables (DDL-gerenciadas — não gerenciadas por DLT)
    # ------------------------------------------------------------------

    def _create_silver_tables(self) -> None:
        cat = self.catalog
        bucket = self.lakehouse_bucket
        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_batch (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente origem da transação',
            tx_hash           STRING    COMMENT 'Hash único da transação — chave de deduplicação com a camada streaming',
            block_number      BIGINT    COMMENT 'Número do bloco Ethereum que contém a transação',
            timestamp         TIMESTAMP COMMENT 'Timestamp da transação extraído do Etherscan',
            from_address      STRING    COMMENT 'Endereço EOA remetente (Externally Owned Account)',
            to_address        STRING    COMMENT 'Endereço do contrato ou EOA receptor',
            value             STRING    COMMENT 'Valor transferido em Wei como string (preserva precisão de 256 bits)',
            gas_used          BIGINT    COMMENT 'Gas consumido pela transação (receipt.gasUsed do Etherscan)',
            ethereum_value    DOUBLE    COMMENT 'Valor convertido de Wei para ETH (value ÷ 1e18)',
            ingestion_date    DATE      COMMENT 'Data de execução do job batch Silver — chave de partição Delta',
            processed_ts      TIMESTAMP COMMENT 'Timestamp UTC de quando o job batch Silver processou este registro'
          )
          COMMENT 'Silver EXTERNAL: transações de contratos populares processadas pelo pipeline batch Bronze→Silver. Deduplicadas por tx_hash em relação à camada streaming.'
          USING DELTA
          PARTITIONED BY (ingestion_date)
          LOCATION 's3://{bucket}/s_apps/transactions_batch'
          TBLPROPERTIES ('quality' = 'silver')
        """)
        _log.info("Table ensured: %s.s_apps.transactions_batch", cat)

    # ------------------------------------------------------------------
    # RLS — Row-Level Security via Unity Catalog Column Masks / Row Filters
    # ------------------------------------------------------------------

    def _apply_rls(self, admin_group: str) -> None:
        cat = self.catalog
        self._sql(f"""
          CREATE OR REPLACE FUNCTION `{cat}`.g_api_keys.api_keys_visibility_filter(api_key_name STRING)
          COMMENT 'Filtro de linha Unity Catalog: retorna TRUE somente para membros do grupo {admin_group}. Aplicar como ROW FILTER nas views g_api_keys para ocultar chaves de API de usuários não-admin.'
          RETURN is_account_group_member('{admin_group}')
        """)
        _log.info("RLS function ensured: %s.g_api_keys.api_keys_visibility_filter", cat)

        # SET ROW FILTER requer que as DLT Materialized Views já existam.
        # try/except garante idempotência no setup inicial (antes do DLT rodar).
        for view in ("etherscan_consumption", "web3_keys_consumption"):
            try:
                self._sql(f"""
                  ALTER TABLE `{cat}`.g_api_keys.{view}
                  SET ROW FILTER `{cat}`.g_api_keys.api_keys_visibility_filter ON (api_key_name)
                """)
                _log.info("Row filter applied to %s.g_api_keys.%s", cat, view)
            except Exception as exc:
                _log.warning(
                    "Cannot apply row filter to %s.g_api_keys.%s (DLT view may not exist yet): %s",
                    cat, view, str(exc)[:200],
                )

    # ------------------------------------------------------------------
    # DLT table comments — ALTER TABLE / ALTER COLUMN após pipeline rodar
    # ------------------------------------------------------------------

    def _alter(self, table: str, col: str, comment: str) -> None:
        cat = self.catalog
        escaped = comment.replace("'", "\\'")
        self._sql(
            f"ALTER TABLE `{cat}`.{table} ALTER COLUMN {col} COMMENT '{escaped}'"
        )

    def _table_comment(self, table: str, comment: str) -> None:
        cat = self.catalog
        escaped = comment.replace("'", "\\'")
        self._sql(f"COMMENT ON TABLE `{cat}`.{table} IS '{escaped}'")

    def _apply_dlt_table_comments(self) -> None:
        """
        Aplica comentários em todas as tabelas e colunas DLT-gerenciadas via ALTER TABLE.
        Executa após o pipeline DLT ter rodado ao menos uma vez.
        Usa try/except por tabela para não abortar caso alguma ainda não exista.
        """

        # ── Bronze b_ethereum.b_blocks_data ─────────────────────────────────
        # Schema inferido pelo Auto Loader (cloudFiles, NDJSON Firehose).
        # Campos em camelCase conforme produzidos pelo Job 3 (block_data_crawler).
        _tbl = "b_ethereum.b_blocks_data"
        try:
            self._table_comment(_tbl,
                "Bronze DLT: dados brutos dos blocos Ethereum entregues via Kinesis → Firehose → S3 (NDJSON). "
                "Schema inferido pelo Auto Loader a partir do stream mainnet-blocks-data.")
            for col, cmt in [
                ("number",           "Número sequencial do bloco na chain principal (hex string da API Web3)"),
                ("hash",             "Hash SHA3-256 do cabeçalho do bloco (0x...)"),
                ("parentHash",       "Hash do bloco pai — encadeamento da blockchain"),
                ("timestamp",        "Unix timestamp do bloco em segundos (epoch) conforme definido pelo miner"),
                ("miner",            "Endereço Ethereum do validador/miner que produziu o bloco"),
                ("difficulty",       "Dificuldade de mineração do bloco (hexadecimal string; zero após The Merge)"),
                ("totalDifficulty",  "Dificuldade total acumulada da chain até este bloco (obsoleto após The Merge)"),
                ("nonce",            "Nonce de prova de trabalho (PoW) — '0x0000000000000000' após The Merge"),
                ("size",             "Tamanho do bloco em bytes"),
                ("baseFeePerGas",    "Taxa base por gas em Wei — introduzida pelo EIP-1559 (London fork, ago/2021)"),
                ("gasLimit",         "Limite máximo de gas permitido no bloco (definido pelo validador)"),
                ("gasUsed",          "Total de gas efetivamente consumido por todas as transações do bloco"),
                ("logsBloom",        "Bloom filter de 2048 bits dos logs das transações — usado para filtragem rápida"),
                ("extraData",        "Campo de dados extras definido pelo miner/validador (hex, até 32 bytes)"),
                ("transactionsRoot", "Raiz da Merkle tree das transações do bloco"),
                ("stateRoot",        "Raiz da Merkle-Patricia trie do estado global após este bloco"),
                ("transactions",     "Array de hashes ou objetos de transação incluídos no bloco"),
                ("withdrawals",      "Array de saques da Beacon Chain (EIP-4895, Shanghai/Capella, abr/2023)"),
                ("_ingested_at",     "Timestamp UTC de quando o registro foi lido pelo Auto Loader"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Bronze b_ethereum.b_transactions_data ───────────────────────────
        _tbl = "b_ethereum.b_transactions_data"
        try:
            self._table_comment(_tbl,
                "Bronze DLT: dados brutos das transações Ethereum via Kinesis → Firehose → S3 (NDJSON). "
                "Schema inferido pelo Auto Loader a partir do stream mainnet-transactions-data.")
            for col, cmt in [
                ("hash",             "Hash único da transação (0x...) — identificador primário na blockchain"),
                ("blockNumber",      "Número do bloco que inclui esta transação (hex string)"),
                ("blockHash",        "Hash do bloco que contém esta transação"),
                ("transactionIndex", "Posição ordinal da transação dentro do bloco (0-indexed)"),
                ("from",             "Endereço EOA remetente — criador e assinante da transação"),
                ("to",               "Endereço receptor (contrato ou EOA). NULL em transações de deploy de contrato"),
                ("value",            "Valor de ETH transferido em Wei (hexadecimal string — preserva 256 bits)"),
                ("input",            "Payload da transação: seletor de função (4 bytes) + parâmetros ABI-encoded. '0x' em transferências P2P"),
                ("gas",              "Gas limit definido pelo remetente para esta transação"),
                ("gasPrice",         "Preço do gas em Wei definido pelo remetente (pre-EIP-1559) ou maxFeePerGas"),
                ("nonce",            "Contador sequencial de transações enviadas pelo endereço remetente — garante unicidade e ordenação"),
                ("v",                "Componente de recuperação da assinatura ECDSA (parity bit)"),
                ("r",                "Componente R da assinatura ECDSA secp256k1"),
                ("s",                "Componente S da assinatura ECDSA secp256k1"),
                ("type",             "Tipo de transação EIP-2718: 0=legacy, 1=EIP-2930 (access list), 2=EIP-1559 (fee market)"),
                ("accessList",       "Lista de endereços e storage slots pré-aquecidos (EIP-2930) para redução de gas"),
                ("_ingested_at",     "Timestamp UTC de quando o registro foi lido pelo Auto Loader"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Bronze b_ethereum.b_transactions_decoded ────────────────────────
        _tbl = "b_ethereum.b_transactions_decoded"
        try:
            self._table_comment(_tbl,
                "Bronze DLT: inputs de transações Ethereum decodificados via ABI/4byte.directory. "
                "Produzido pelo Job 5 (txs_input_decoder) via Kinesis → Firehose → S3.")
            for col, cmt in [
                ("tx_hash",          "Hash da transação — chave de junção com b_transactions_data"),
                ("contract_address", "Endereço do contrato cujo ABI foi usado para a decodificação"),
                ("method",           "Nome do método Solidity chamado (ex: 'transfer', 'swap')"),
                ("parms",            "Parâmetros decodificados como JSON string: lista de {name, type, value}"),
                ("decode_type",      "Qualidade da decodificação: 'full'=ABI completo via Etherscan, 'full_4byte'=ABI via 4byte.directory, 'partial'=apenas nome do método, 'unknown'=seletor hex não reconhecido"),
                ("_ingested_at",     "Timestamp UTC de quando o registro foi lido pelo Auto Loader"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Bronze b_app_logs.b_app_logs_data ───────────────────────────────
        _tbl = "b_app_logs.b_app_logs_data"
        try:
            self._table_comment(_tbl,
                "Bronze DLT: logs das aplicações on-chain via CloudWatch Logs → Firehose → S3. "
                "Payload double-gzipped decomprimido por UDF PySpark. Schema: campos JSON de log estruturado.")
            for col, cmt in [
                ("timestamp",       "Unix timestamp em milissegundos do evento de log conforme o CloudWatch"),
                ("logger",          "Nome da aplicação emissora do log (ex: MINED_BLOCKS_EVENTS, CONTRACT_TRANSACTIONS_CRAWLER)"),
                ("level",           "Nível de severidade do log: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
                ("filename",        "Nome do arquivo Python que emitiu o log (ex: '3_block_data_crawler.py')"),
                ("function_name",   "Nome da função Python que emitiu o log"),
                ("message",         "Conteúdo da mensagem de log — pode conter dados estruturados separados por ';'"),
                ("log_group",       "CloudWatch Log Group de origem (ex: /apps/dm-chain-explorer-dev)"),
                ("log_stream",      "CloudWatch Log Stream de origem (ex: raw_txs_crawler-job-<uuid>)"),
                ("_ingested_at",    "Timestamp UTC de quando o registro foi processado pelo Auto Loader"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Bronze b_app_logs.logs_streaming (Silver DLT em schema b_app_logs)
        # Nota: tabela criada pelo pipeline dm-app-logs com target=b_app_logs
        _tbl = "b_app_logs.logs_streaming"
        try:
            self._table_comment(_tbl,
                "Silver DLT: logs filtrados das aplicações de streaming (MINED_BLOCKS_EVENTS, ORPHAN_BLOCKS_CRAWLER, "
                "BLOCK_DATA_CRAWLER, RAW_TXS_CRAWLER, TRANSACTION_INPUT_DECODER). Partição natural por _ingested_at.")
            for col, cmt in [
                ("event_ts_epoch",  "Timestamp do evento em milissegundos Unix (campo 'timestamp' do CloudWatch)"),
                ("event_time",      "Timestamp do evento convertido para TIMESTAMP — facilita filtros temporais"),
                ("logger",          "Nome da aplicação de streaming (ex: MINED_BLOCKS_EVENTS)"),
                ("level",           "Nível de severidade: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
                ("filename",        "Arquivo Python que emitiu o log"),
                ("function_name",   "Função Python que emitiu o log"),
                ("message",         "Mensagem de log — pode conter campos estruturados separados por ';'"),
                ("_ingested_at",    "Timestamp UTC de ingestão — herdado do Bronze b_app_logs_data"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Bronze b_app_logs.logs_batch (Silver DLT em schema b_app_logs) ──
        _tbl = "b_app_logs.logs_batch"
        try:
            self._table_comment(_tbl,
                "Silver DLT: logs filtrados das aplicações batch (CONTRACT_TRANSACTIONS_CRAWLER). "
                "Partição natural por _ingested_at.")
            for col, cmt in [
                ("event_ts_epoch",  "Timestamp do evento em milissegundos Unix (campo 'timestamp' do CloudWatch)"),
                ("event_time",      "Timestamp do evento convertido para TIMESTAMP"),
                ("logger",          "Nome da aplicação batch (ex: CONTRACT_TRANSACTIONS_CRAWLER)"),
                ("level",           "Nível de severidade: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
                ("filename",        "Arquivo Python que emitiu o log"),
                ("function_name",   "Função Python que emitiu o log"),
                ("message",         "Mensagem de log — pode conter campos estruturados separados por ';'"),
                ("_ingested_at",    "Timestamp UTC de ingestão — herdado do Bronze b_app_logs_data"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Silver s_apps.blocks_fast ────────────────────────────────────────
        _tbl = "s_apps.blocks_fast"
        try:
            self._table_comment(_tbl,
                "Silver DLT: dados completos dos blocos Ethereum com campos normalizados para snake_case. "
                "Lê de b_ethereum.b_blocks_data via stream. Inclui array de withdrawals da Beacon Chain.")
            for col, cmt in [
                ("block_number",       "Número sequencial do bloco na chain"),
                ("block_hash",         "Hash do cabeçalho do bloco (0x...)"),
                ("parent_hash",        "Hash do bloco pai — garante o encadeamento imutável"),
                ("block_time",         "Timestamp do bloco como TIMESTAMP SQL (convertido de Unix epoch)"),
                ("block_timestamp",    "Unix timestamp do bloco em segundos (epoch original do JSON)"),
                ("miner",              "Endereço do validador/miner que produziu o bloco"),
                ("difficulty",         "Dificuldade de mineração (zero após The Merge — set/2022)"),
                ("total_difficulty",   "Dificuldade acumulada total da chain até este bloco"),
                ("nonce",              "Nonce PoW — '0x0000000000000000' após The Merge"),
                ("size",               "Tamanho do bloco em bytes"),
                ("base_fee_per_gas",   "Taxa base por gas em Wei (EIP-1559) — queimada pela rede"),
                ("gas_limit",          "Gas limit do bloco definido pelo validador"),
                ("gas_used",           "Gas total consumido por todas as transações do bloco"),
                ("logs_bloom",         "Bloom filter dos logs do bloco para consulta O(1) de eventos"),
                ("extra_data",         "Campo livre do miner/validador em hexadecimal (até 32 bytes)"),
                ("transactions_root",  "Raiz Merkle das transações — permite prova de inclusão"),
                ("state_root",         "Raiz do estado global Ethereum após aplicar este bloco"),
                ("transaction_count",  "Quantidade de transações incluídas no bloco (len do array transactions)"),
                ("transactions",       "Array de hashes de transações incluídas no bloco"),
                ("withdrawals",        "Array de structs de saques ETH da Beacon Chain (EIP-4895)"),
                ("_ingested_at",       "Timestamp UTC de ingestão pelo Auto Loader"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Silver s_apps.transactions_fast ─────────────────────────────────
        _tbl = "s_apps.transactions_fast"
        try:
            self._table_comment(_tbl,
                "Silver DLT: transações Ethereum com campos raw normalizados — sem input decodificado. "
                "Particionado por event_date para otimizar queries temporais. "
                "Decodificação disponível em txs_inputs_decoded_fast e transactions_ethereum.")
            for col, cmt in [
                ("tx_hash",          "Hash único da transação (0x...) — chave primária na blockchain Ethereum"),
                ("block_number",     "Número do bloco que inclui esta transação"),
                ("block_hash",       "Hash do bloco que contém esta transação"),
                ("transaction_index","Posição ordinal da transação dentro do bloco (0-indexed)"),
                ("from_address",     "Endereço EOA remetente — assinante e pagador do gas"),
                ("to_address",       "Endereço receptor. NULL em transações de deploy de contrato inteligente"),
                ("value",            "Valor de ETH transferido em Wei (hexadecimal string — 256 bits)"),
                ("input",            "Payload da transação: seletor 4 bytes + parâmetros. '0x' em transferências P2P"),
                ("gas",              "Gas limit definido pelo remetente (upper bound do gas consumido)"),
                ("gas_price",        "Preço do gas em Wei (ou maxFeePerGas em EIP-1559)"),
                ("nonce",            "Contador de transações do remetente — garante unicidade e evita replay"),
                ("v",                "Parity bit da assinatura ECDSA para recuperação do endereço"),
                ("r",                "Componente R da assinatura ECDSA secp256k1"),
                ("s",                "Componente S da assinatura ECDSA secp256k1"),
                ("tx_type",          "Tipo EIP-2718: 0=legacy, 1=access_list (EIP-2930), 2=fee_market (EIP-1559)"),
                ("access_list",      "Lista de endereços/storage pré-aquecidos EIP-2930 para redução de gas"),
                ("_ingested_at",     "Timestamp UTC de ingestão pelo Auto Loader"),
                ("event_date",       "Data derivada de _ingested_at — chave de partição Delta"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Silver s_apps.txs_inputs_decoded_fast ───────────────────────────
        _tbl = "s_apps.txs_inputs_decoded_fast"
        try:
            self._table_comment(_tbl,
                "Silver DLT: inputs de transações Ethereum decodificados em tempo real pelo Job 5. "
                "JOIN com transactions_fast por tx_hash produz transactions_ethereum.")
            for col, cmt in [
                ("tx_hash",          "Hash da transação — chave de join com transactions_fast"),
                ("contract_address", "Endereço do contrato cujo ABI foi usado para decodificação"),
                ("method",           "Nome do método Solidity chamado (ex: 'transfer', 'swapExactTokensForTokens')"),
                ("parms",            "Parâmetros decodificados como JSON string: [{name, type, value}, ...]"),
                ("decode_type",      "Qualidade: 'full'=ABI Etherscan completo, 'full_4byte'=4byte.directory, 'partial'=só método, 'unknown'=não reconhecido"),
                ("_ingested_at",     "Timestamp UTC de ingestão pelo Auto Loader"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Silver s_apps.transactions_ethereum ─────────────────────────────
        _tbl = "s_apps.transactions_ethereum"
        try:
            self._table_comment(_tbl,
                "Silver DLT: transações Ethereum enriquecidas via Stream-Static JOIN. "
                "Une transactions_fast + txs_inputs_decoded_fast + blocks_fast. "
                "Fonte principal para Gold MVs de análise on-chain.")
            for col, cmt in [
                ("tx_hash",          "Hash único da transação"),
                ("block_number",     "Número do bloco"),
                ("block_hash",       "Hash do bloco"),
                ("transaction_index","Posição ordinal no bloco"),
                ("from_address",     "Endereço EOA remetente"),
                ("to_address",       "Endereço receptor (NULL em deploys)"),
                ("value",            "Valor transferido em Wei (hexadecimal string)"),
                ("input",            "Payload raw da transação em hexadecimal"),
                ("gas",              "Gas limit da transação"),
                ("gas_price",        "Preço do gas em Wei"),
                ("nonce",            "Nonce do remetente"),
                ("tx_type",          "Tipo EIP-2718: 0=legacy, 1=access_list, 2=fee_market"),
                ("tx_timestamp",     "Timestamp da transação derivado do bloco (from_unixtime do block_timestamp)"),
                ("block_gas_limit",  "Gas limit do bloco em que esta transação está incluída"),
                ("block_gas_used",   "Gas total consumido pelo bloco — referência para calcular utilização"),
                ("base_fee_per_gas", "Taxa base do bloco em Wei (EIP-1559) — porção queimada do gas price"),
                ("contract_address", "Contrato cujo ABI foi usado para decodificação (JOIN com decoded)"),
                ("method",           "Nome do método Solidity chamado (NULL se não decodificado)"),
                ("parms",            "Parâmetros decodificados como JSON string (NULL se não decodificado)"),
                ("decode_type",      "Qualidade da decodificação (NULL se não decodificado)"),
                ("input_etherscan",  "Input alternativo do Etherscan (placeholder — preenchido futuramente pelo batch)"),
                ("_ingested_at",     "Timestamp UTC de ingestão"),
                ("event_date",       "Data derivada de _ingested_at — chave de partição"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Silver s_apps.blocks_withdrawals ────────────────────────────────
        _tbl = "s_apps.blocks_withdrawals"
        try:
            self._table_comment(_tbl,
                "Silver DLT: saques ETH da Beacon Chain (EIP-4895, Shanghai/Capella abr/2023). "
                "Explode de blocks_fast.withdrawals — uma linha por withdrawal por bloco. "
                "Amount em Gwei (÷1e9 = ETH). Máx 16 saques por bloco.")
            for col, cmt in [
                ("block_number",       "Número do bloco em que o saque foi processado"),
                ("block_timestamp",    "Timestamp do bloco como string formatada (yyyy-MM-dd HH:mm:ss)"),
                ("miner",              "Endereço do validador que produziu o bloco"),
                ("withdrawal_index",   "Índice global sequencial do saque na Beacon Chain (único por saque)"),
                ("validator_index",    "Índice do validador na Beacon Chain que realizou o saque"),
                ("withdrawal_address", "Endereço Ethereum de destino configurado pelo validador para receber o ETH"),
                ("amount_gwei",        "Valor do saque em Gwei (1 Gwei = 1e9 Wei)"),
                ("amount_eth",         "Valor do saque convertido para ETH (amount_gwei ÷ 1e9)"),
                ("_ingested_at",       "Timestamp UTC de ingestão do bloco pai"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold s_apps.popular_contracts_ranking ───────────────────────────
        _tbl = "s_apps.popular_contracts_ranking"
        try:
            self._table_comment(_tbl,
                "Gold MV: top 100 contratos Ethereum com mais transações na última hora. "
                "Fonte para o job batch de captura de transações históricas (contracts_ingestion Lambda).")
            for col, cmt in [
                ("contract_address", "Endereço do contrato inteligente"),
                ("tx_count",         "Total de transações recebidas pelo contrato na última hora"),
                ("unique_senders",   "Número de endereços EOA distintos que interagiram com o contrato na última hora"),
                ("first_seen",       "Timestamp da primeira transação para este contrato no período"),
                ("last_seen",        "Timestamp da última transação para este contrato no período"),
                ("computed_at",      "Timestamp UTC de quando esta Materialized View foi recalculada"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold s_apps.peer_to_peer_txs ────────────────────────────────────
        _tbl = "s_apps.peer_to_peer_txs"
        try:
            self._table_comment(_tbl,
                "Gold MV: transferências ETH diretas entre endereços EOA (Externally Owned Accounts). "
                "Identificadas por campo input vazio/nulo/'0x' e to_address não nulo. "
                "Exclui interações com contratos e deploys.")
            for col, cmt in [
                ("tx_hash",        "Hash único da transação P2P"),
                ("block_number",   "Número do bloco que contém a transação"),
                ("from_address",   "EOA remetente do ETH"),
                ("to_address",     "EOA receptor do ETH"),
                ("value",          "Valor transferido em Wei (hexadecimal string)"),
                ("gas",            "Gas limit da transação (21000 para P2P padrão)"),
                ("gas_price",      "Preço do gas em Wei pago pelo remetente"),
                ("tx_timestamp",   "Timestamp da transação derivado do bloco"),
                ("base_fee_per_gas","Taxa base do bloco em Wei (EIP-1559)"),
                ("_ingested_at",   "Timestamp UTC de ingestão"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold s_apps.ethereum_gas_consume ───────────────────────────────
        _tbl = "s_apps.ethereum_gas_consume"
        try:
            self._table_comment(_tbl,
                "Gold MV: consumo de gas por transação Ethereum com classificação de tipo. "
                "Tipos: peer_to_peer (input vazio), contract_deploy (to nulo), contract_interaction (demais).")
            for col, cmt in [
                ("block_number",           "Número do bloco"),
                ("tx_hash",                "Hash da transação"),
                ("from_address",           "EOA remetente"),
                ("to_address",             "Endereço receptor (NULL em deploys)"),
                ("value",                  "Valor transferido em Wei"),
                ("gas_price",              "Preço do gas em Wei"),
                ("gas_limit",              "Gas limit definido pelo remetente (campo gas da transação)"),
                ("tx_timestamp",           "Timestamp da transação"),
                ("type_transaction",       "Classificação: 'peer_to_peer' | 'contract_interaction' | 'contract_deploy'"),
                ("block_gas_limit",        "Gas limit do bloco"),
                ("block_gas_used",         "Gas total efetivamente consumido no bloco"),
                ("gas_pct_of_block",       "Porcentagem do gas do bloco que o gas_limit desta tx representa (gas / block_gas_used × 100)"),
                ("base_fee_per_gas",       "Taxa base do bloco em Wei (queimada pela rede, EIP-1559)"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold s_apps.transactions_lambda ────────────────────────────────
        _tbl = "s_apps.transactions_lambda"
        try:
            self._table_comment(_tbl,
                "Gold MV: visão Lambda unindo streaming real-time (transactions_ethereum) e batch histórico "
                "(popular_contracts_txs) das transações dos contratos mais populares. "
                "Deduplicada por tx_hash com prioridade: full > full_4byte > partial > batch > unknown.")
            for col, cmt in [
                ("tx_hash",          "Hash da transação — chave de deduplicação entre camadas"),
                ("block_number",     "Número do bloco"),
                ("from_address",     "EOA remetente"),
                ("contract_address", "Endereço do contrato receptor — contratos populares do ranking"),
                ("value",            "Valor transferido em Wei"),
                ("gas",              "Gas limit (streaming) ou gas_used (batch Etherscan)"),
                ("gas_price",        "Preço do gas em Wei (NULL na camada batch)"),
                ("input",            "Payload raw da transação em hexadecimal"),
                ("method",           "Nome do método Solidity decodificado (NULL na camada batch)"),
                ("parms",            "Parâmetros decodificados como JSON (NULL na camada batch)"),
                ("decode_type",      "Qualidade da decodificação (NULL na camada batch)"),
                ("input_etherscan",  "Input alternativo do Etherscan (futuro enriquecimento)"),
                ("event_time",       "Timestamp do evento (tx_timestamp do streaming, timestamp do batch)"),
                ("source_layer",     "Origem do registro: 'streaming' (real-time) ou 'batch' (Etherscan histórico)"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold g_network.network_metrics_hourly ───────────────────────────
        _tbl = "g_network.network_metrics_hourly"
        try:
            self._table_comment(_tbl,
                "Gold MV: métricas agregadas da rede Ethereum por hora. "
                "Combina blocks_fast e transactions_fast para calcular TPS, preço de gas e utilização de blocos.")
            for col, cmt in [
                ("hour_bucket",                "Janela temporal horária (date_trunc hora) — chave de agrupamento"),
                ("block_count",                "Número de blocos produzidos na hora"),
                ("tx_count",                   "Total de transações na hora (de transactions_fast; fallback de blocks.transaction_count)"),
                ("tps_avg",                    "TPS médio da hora: tx_count ÷ 3600 segundos"),
                ("avg_gas_price_gwei",         "Preço médio do gas em Gwei (gas_price ÷ 1e9) nas transações da hora"),
                ("avg_block_gas_used",         "Média de gas consumido por bloco na hora"),
                ("avg_block_gas_limit",        "Média do gas limit por bloco na hora"),
                ("avg_block_utilization_pct",  "Utilização média do bloco na hora: (avg_gas_used ÷ avg_gas_limit) × 100"),
                ("avg_txs_per_block",          "Média de transações por bloco na hora"),
                ("computed_at",               "Timestamp UTC do último recálculo da Materialized View"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold g_api_keys.etherscan_consumption ───────────────────────────
        _tbl = "g_api_keys.etherscan_consumption"
        try:
            self._table_comment(_tbl,
                "Gold MV (RLS protegida): consumo de API keys Etherscan por janela de tempo. "
                "Agrega chamadas de logs_streaming + logs_batch por api_key_name com contadores por status. "
                "Acesso restrito a admins via api_keys_visibility_filter.")
            for col, cmt in [
                ("api_key_name",      "Nome da API key Etherscan conforme SSM Parameter Store"),
                ("calls_total",       "Total acumulado de chamadas realizadas por esta chave"),
                ("calls_ok_total",    "Total de chamadas com status='ok'"),
                ("calls_error_total", "Total de chamadas com status de erro"),
                ("calls_1h",          "Chamadas realizadas na última 1 hora"),
                ("calls_2h",          "Chamadas realizadas nas últimas 2 horas"),
                ("calls_12h",         "Chamadas realizadas nas últimas 12 horas"),
                ("calls_24h",         "Chamadas realizadas nas últimas 24 horas"),
                ("calls_48h",         "Chamadas realizadas nas últimas 48 horas"),
                ("last_call_at",      "Timestamp da última chamada registrada para esta chave"),
                ("computed_at",       "Timestamp UTC do último recálculo da Materialized View"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])

        # ── Gold g_api_keys.web3_keys_consumption ───────────────────────────
        _tbl = "g_api_keys.web3_keys_consumption"
        try:
            self._table_comment(_tbl,
                "Gold MV (RLS protegida): consumo de API keys Web3 (Alchemy/Infura) por janela de tempo. "
                "Agrega chamadas de logs_streaming + logs_batch por api_key_name e vendor. "
                "Acesso restrito a admins via api_keys_visibility_filter.")
            for col, cmt in [
                ("api_key_name",      "Nome da API key Web3 conforme SSM Parameter Store (ex: alchemy-key-1)"),
                ("vendor",            "Provedor Web3: 'alchemy', 'infura' ou 'unknown'"),
                ("calls_total",       "Total acumulado de chamadas realizadas por esta chave"),
                ("calls_ok_total",    "Total de chamadas bem-sucedidas (sem erro HTTP ou de cliente)"),
                ("calls_error_total", "Total de chamadas com erro (HTTP error ou exceção de cliente)"),
                ("calls_1h",          "Chamadas realizadas na última 1 hora"),
                ("calls_2h",          "Chamadas realizadas nas últimas 2 horas"),
                ("calls_12h",         "Chamadas realizadas nas últimas 12 horas"),
                ("calls_24h",         "Chamadas realizadas nas últimas 24 horas"),
                ("calls_48h",         "Chamadas realizadas nas últimas 48 horas"),
                ("last_call_at",      "Timestamp da última chamada registrada para esta combinação chave+vendor"),
                ("computed_at",       "Timestamp UTC do último recálculo da Materialized View"),
            ]:
                self._alter(_tbl, col, cmt)
            _log.info("Comments applied: %s", _tbl)
        except Exception as exc:
            _log.warning("Skipping %s (table may not exist yet): %s", _tbl, str(exc)[:200])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Setup DDL for DD Chain Explorer Unity Catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--catalog", required=True,
                        help="Unity Catalog name (ex: dev, hml, dd_chain_explorer)")
    parser.add_argument("--lakehouse-s3-bucket", required=True,
                        help="S3 bucket for EXTERNAL table locations")
    parser.add_argument("--admin-group", default="admins",
                        help="Unity Catalog group for RLS (default: admins)")
    parser.add_argument("--drop", action="store_true",
                        help="DROP SCHEMA CASCADE on all schemas before setup")
    parser.add_argument("--comments-only", action="store_true",
                        help="Only apply ALTER COLUMN comments (skip CREATE)")
    parser.add_argument("--warehouse-id",
                        help="SQL Warehouse ID for DEV/Free Edition execution")
    parser.add_argument("--host",
                        help="Databricks workspace URL (defaults to DATABRICKS_HOST env)")
    args = parser.parse_args()

    # Build executor: Spark if available, warehouse otherwise
    if args.warehouse_id:
        executor = _build_warehouse_executor(args.warehouse_id, args.host)
        _log.info("Using Databricks Statements API (warehouse_id=%s)", args.warehouse_id)
    else:
        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            executor = _SparkExecutor(spark)
            _log.info("Using SparkSession executor")
        except ImportError as exc:
            raise RuntimeError(
                "PySpark not available and --warehouse-id not provided. "
                "Pass --warehouse-id for DEV/Free Edition execution."
            ) from exc

    ddl = DDChainExplorerDDL(executor, args.catalog, args.lakehouse_s3_bucket)

    if args.drop:
        ddl.drop_all()

    if args.comments_only:
        ddl.apply_comments()
    else:
        ddl.setup_all(args.admin_group)
        ddl.apply_comments()


if __name__ == "__main__":
    main()
