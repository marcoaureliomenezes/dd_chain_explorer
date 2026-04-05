"""setup_ddl.py — DDL para DD Chain Explorer Unity Catalog.

Cria schemas e tabelas EXTERNAL DDL-gerenciadas de forma idempotente.
Executado como spark_python_task via workflow dm-ddl-setup (DABs).

Flags:
  --catalog               Catálogo Unity Catalog (obrigatório)
  --lakehouse-s3-bucket   Bucket S3 para tabelas EXTERNAL (obrigatório)
  --drop                  Remove dados S3 + DROP SCHEMA CASCADE antes de criar
"""

from __future__ import annotations

import argparse
import logging

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ---------------------------------------------------------------------------
# DDL class
# ---------------------------------------------------------------------------

class DDChainExplorerDDL:
    """
    DDL idempotente para DD Chain Explorer Unity Catalog.

    Gerencia somente as tabelas EXTERNAL (DDL-gerenciadas):
      - b_ethereum.popular_contracts_txs
      - s_apps.transactions_batch

    Tabelas DLT-gerenciadas (Bronze/Silver/Gold) são criadas e gerenciadas
    pelos pipelines DLT. Este script não as toca.
    """

    ALL_SCHEMAS = ("b_ethereum", "b_app_logs", "s_apps", "s_logs", "g_network", "g_api_keys")

    # EXTERNAL table locations — usados no CREATE e no drop de dados S3
    EXTERNAL_TABLES = {
        "b_ethereum.popular_contracts_txs": "b_ethereum/popular_contracts_txs",
        "s_apps.transactions_batch":        "s_apps/transactions_batch",
    }

    def __init__(self, catalog: str, lakehouse_bucket: str) -> None:
        self.catalog = catalog
        self.lakehouse_bucket = lakehouse_bucket

    def _sql(self, statement: str) -> None:
        _log.debug("SQL: %s", statement[:120].replace("\n", " "))
        spark.sql(statement)  # noqa: F821 — spark é injetado pelo Databricks runtime

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def drop_all(self) -> None:
        """Remove dados S3 das tabelas EXTERNAL + DROP SCHEMA CASCADE."""
        cat = self.catalog
        for rel_path in self.EXTERNAL_TABLES.values():
            location = f"s3://{self.lakehouse_bucket}/{rel_path}"
            try:
                dbutils.fs.rm(location, recurse=True)  # noqa: F821
                _log.info("Removed S3 data: %s", location)
            except Exception as exc:
                _log.warning("Could not remove %s (may not exist): %s", location, exc)
        for schema in self.ALL_SCHEMAS:
            self._sql(f"DROP SCHEMA IF EXISTS `{cat}`.{schema} CASCADE")
            _log.info("Dropped schema: %s.%s", cat, schema)

    def setup_all(self) -> None:
        """Criação idempotente: schemas + tabelas EXTERNAL."""
        self._create_schemas()
        self._create_external_tables()
        _log.info("DDL setup complete for catalog '%s'", self.catalog)

    # ------------------------------------------------------------------
    # Schemas
    # ------------------------------------------------------------------

    def _create_schemas(self) -> None:
        cat = self.catalog
        for schema in self.ALL_SCHEMAS:
            self._sql(f"CREATE SCHEMA IF NOT EXISTS `{cat}`.{schema}")
            _log.info("Schema ensured: %s.%s", cat, schema)

    # ------------------------------------------------------------------
    # EXTERNAL tables (DDL-gerenciadas — não gerenciadas pelo DLT)
    # ------------------------------------------------------------------

    def _create_external_tables(self) -> None:
        cat = self.catalog
        bucket = self.lakehouse_bucket

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.popular_contracts_txs (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente na rede Ethereum (0x...)',
            tx_hash           STRING    COMMENT 'Hash único da transação Ethereum (0x...)',
            block_number      BIGINT    COMMENT 'Número do bloco que contém a transação',
            timestamp         TIMESTAMP COMMENT 'Timestamp da transação conforme reportado pela API Etherscan',
            from_address      STRING    COMMENT 'Endereço EOA que originou a transação',
            to_address        STRING    COMMENT 'Endereço de destino — contrato ou EOA receptor',
            value             STRING    COMMENT 'Valor em Wei como string (preserva precisão de 256 bits)',
            gas_used          BIGINT    COMMENT 'Gas efetivamente consumido (receipt.gasUsed)',
            input             STRING    COMMENT 'Payload hexadecimal enviado ao contrato (seletor 4 bytes + params ABI-encoded)',
            ingestion_date    DATE      COMMENT 'Data de execução do job batch — chave de partição Delta'
          )
          COMMENT 'Bronze EXTERNAL: transações de contratos populares ingeridas via job batch da API Etherscan (hourly).'
          USING DELTA
          PARTITIONED BY (ingestion_date)
          LOCATION 's3://{bucket}/b_ethereum/popular_contracts_txs'
          TBLPROPERTIES ('quality' = 'bronze')
        """)
        _log.info("Table ensured: %s.b_ethereum.popular_contracts_txs", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_batch (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente origem da transação',
            tx_hash           STRING    COMMENT 'Hash único da transação — chave de deduplicação com a camada streaming',
            block_number      BIGINT    COMMENT 'Número do bloco Ethereum que contém a transação',
            timestamp         TIMESTAMP COMMENT 'Timestamp da transação extraído do Etherscan',
            from_address      STRING    COMMENT 'Endereço EOA remetente',
            to_address        STRING    COMMENT 'Endereço do contrato ou EOA receptor',
            value             STRING    COMMENT 'Valor em Wei como string (preserva precisão de 256 bits)',
            gas_used          BIGINT    COMMENT 'Gas consumido (receipt.gasUsed do Etherscan)',
            ethereum_value    DOUBLE    COMMENT 'Valor convertido de Wei para ETH (value ÷ 1e18)',
            ingestion_date    DATE      COMMENT 'Data de execução do job batch Silver — chave de partição Delta',
            processed_ts      TIMESTAMP COMMENT 'Timestamp UTC de quando o job batch Silver processou este registro'
          )
          COMMENT 'Silver EXTERNAL: transações de contratos populares processadas pelo pipeline batch Bronze→Silver.'
          USING DELTA
          PARTITIONED BY (ingestion_date)
          LOCATION 's3://{bucket}/s_apps/transactions_batch'
          TBLPROPERTIES ('quality' = 'silver')
        """)
        _log.info("Table ensured: %s.s_apps.transactions_batch", cat)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Setup DDL for DD Chain Explorer Unity Catalog")
    parser.add_argument("--catalog", required=True,
                        help="Unity Catalog name (ex: dev, hml, dd_chain_explorer)")
    parser.add_argument("--lakehouse-s3-bucket", required=True,
                        help="S3 bucket for EXTERNAL table locations")
    parser.add_argument("--drop", action="store_true",
                        help="Remove S3 data + DROP SCHEMA CASCADE before setup")
    args = parser.parse_args()

    ddl = DDChainExplorerDDL(args.catalog, args.lakehouse_s3_bucket)

    if args.drop:
        ddl.drop_all()

    ddl.setup_all()


if __name__ == "__main__":
    main()
