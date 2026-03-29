import argparse
import logging

from pyspark.sql import SparkSession

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class DDChainExplorerDDL:
    def __init__(self, spark: SparkSession, catalog: str, lakehouse_bucket: str) -> None:
        self.spark = spark
        self.catalog = catalog
        self.lakehouse_bucket = lakehouse_bucket

    def setup_all(self, admin_group: str = "admins") -> None:
        self._create_schemas()
        self._create_bronze_tables()
        self._create_silver_tables()
        self._apply_rls(admin_group)
        _log.info("DDL setup complete for catalog '%s'", self.catalog)

    def _create_schemas(self) -> None:
        cat = self.catalog
        for schema in ("b_ethereum", "s_apps", "s_logs", "g_api_keys"):
            self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{cat}`.{schema}")
            _log.info("Schema ensured: %s.%s", cat, schema)

    def _create_bronze_tables(self) -> None:
        cat = self.catalog
        bucket = self.lakehouse_bucket
        # kafka_topics_multiplexed é gerenciada pelo DLT — NÃO criar aqui.
        self.spark.sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.popular_contracts_txs (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente na rede Ethereum',
            tx_hash           STRING    COMMENT 'Hash único da transação',
            block_number      BIGINT    COMMENT 'Número do bloco contendo a transação',
            timestamp         TIMESTAMP COMMENT 'Timestamp da transação extraído da API Etherscan',
            from_address      STRING    COMMENT 'Endereço da carteira de origem',
            to_address        STRING    COMMENT 'Endereço da carteira ou contrato de destino',
            value             STRING    COMMENT 'Valor transferido em Wei (string para evitar overflow)',
            gas_used          BIGINT    COMMENT 'Gas consumido pela transação',
            input             STRING    COMMENT 'Dados de entrada codificados em hexadecimal',
            ingestion_date    DATE      COMMENT 'Data de ingestão usada como partição'
          )
          COMMENT 'Transações de contratos populares ingeridas via batch da API Etherscan'
          USING DELTA
          PARTITIONED BY (ingestion_date)
          LOCATION 's3://{bucket}/b_ethereum/popular_contracts_txs'
          TBLPROPERTIES ('quality' = 'bronze')
        """)
        _log.info("Table ensured: %s.b_ethereum.popular_contracts_txs", cat)

    def _create_silver_tables(self) -> None:
        cat = self.catalog
        bucket = self.lakehouse_bucket
        # As tabelas gerenciadas pelo DLT (blocks_fast, transactions_fast, etc.) NÃO são criadas aqui.
        self.spark.sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_batch (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente na rede Ethereum',
            tx_hash           STRING    COMMENT 'Hash único da transação (chave de deduplicação)',
            block_number      BIGINT    COMMENT 'Número do bloco contendo a transação',
            timestamp         TIMESTAMP COMMENT 'Timestamp da transação',
            from_address      STRING    COMMENT 'Endereço da carteira de origem',
            to_address        STRING    COMMENT 'Endereço da carteira ou contrato de destino',
            value             STRING    COMMENT 'Valor transferido em Wei',
            gas_used          BIGINT    COMMENT 'Gas consumido pela transação',
            ethereum_value    DOUBLE    COMMENT 'Valor em ETH convertido de Wei (value / 1e18)',
            ingestion_date    DATE      COMMENT 'Data de ingestão usada como partição',
            processed_ts      TIMESTAMP COMMENT 'Timestamp de processamento pelo job batch Silver'
          )
          COMMENT 'Transações de contratos populares processadas pelo batch Bronze → Silver'
          USING DELTA
          PARTITIONED BY (ingestion_date)
          LOCATION 's3://{bucket}/s_apps/transactions_batch'
          TBLPROPERTIES ('quality' = 'silver')
        """)
        _log.info("Table ensured: %s.s_apps.transactions_batch", cat)

    def _apply_rls(self, admin_group: str) -> None:
        cat = self.catalog
        self.spark.sql(f"""
          CREATE OR REPLACE FUNCTION `{cat}`.g_api_keys.api_keys_visibility_filter(api_key_name STRING)
          COMMENT 'Filtro de linha: permite acesso somente a membros do grupo {admin_group}. Aplicado às views g_api_keys.'
          RETURN is_account_group_member('{admin_group}')
        """)
        _log.info("RLS function ensured: %s.g_api_keys.api_keys_visibility_filter", cat)

        # SET ROW FILTER em DLT Materialized Views requer que o pipeline já tenha rodado.
        # try/except garante idempotência no setup inicial.
        for view in ("etherscan_consumption", "web3_keys_consumption"):
            try:
                self.spark.sql(f"""
                  ALTER TABLE `{cat}`.g_api_keys.{view}
                  SET ROW FILTER `{cat}`.g_api_keys.api_keys_visibility_filter ON (api_key_name)
                """)
                _log.info("Row filter applied to %s.g_api_keys.%s", cat, view)
            except Exception as exc:
                _log.warning(
                    "Cannot apply row filter to %s.g_api_keys.%s (DLT view may not exist yet): %s",
                    cat, view, str(exc)[:150],
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup DDL for DD Chain Explorer Unity Catalog")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--lakehouse-s3-bucket", required=True)
    parser.add_argument("--admin-group", default="admins")
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    DDChainExplorerDDL(spark, args.catalog, args.lakehouse_s3_bucket).setup_all(args.admin_group)


if __name__ == "__main__":
    main()
