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
        self._create_gold_views()
        self._apply_rls(admin_group)
        _log.info("DDL setup complete for catalog '%s'", self.catalog)

    def _create_schemas(self) -> None:
        cat = self.catalog
        for schema in ("b_ethereum", "s_apps", "s_logs", "gold", "g_api_keys"):
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

        self.spark.sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_logs.apps_logs_fast (
            level           STRING    COMMENT 'Nível do log: INFO, WARN, ERROR',
            logger          STRING    COMMENT 'Nome do logger (classe ou módulo)',
            message         STRING    COMMENT 'Mensagem do log',
            timestamp       BIGINT    COMMENT 'Timestamp Unix em milissegundos',
            job_name        STRING    COMMENT 'Nome do job gerador do log (partição)',
            api_key         STRING    COMMENT 'API key associada ao log (mascarada)',
            event_time      TIMESTAMP COMMENT 'Timestamp do evento convertido para UTC',
            kafka_timestamp TIMESTAMP COMMENT 'Timestamp de ingestão no tópico Kafka'
          )
          COMMENT 'Logs de aplicação do Lambda consumer Kafka ingeridos pelo pipeline DLT'
          USING DELTA
          PARTITIONED BY (job_name)
          LOCATION 's3://{bucket}/s_logs/apps_logs_fast'
          TBLPROPERTIES ('quality' = 'silver')
        """)
        _log.info("Table ensured: %s.s_logs.apps_logs_fast", cat)

    def _create_gold_views(self) -> None:
        cat = self.catalog
        self.spark.sql(f"""
          CREATE OR REPLACE VIEW `{cat}`.gold.blocks_with_tx_count
          COMMENT 'Blocos Ethereum com contagem de transações por bloco'
          AS
          SELECT
            b.block_number,
            b.block_hash,
            b.miner,
            b.gas_used,
            b.gas_limit,
            b.base_fee_per_gas,
            b.transaction_count,
            b.block_time AS event_time
          FROM `{cat}`.s_apps.blocks_fast b
        """)
        _log.info("View ensured: %s.gold.blocks_with_tx_count", cat)

        self.spark.sql(f"""
          CREATE OR REPLACE VIEW `{cat}`.gold.top_contracts_by_volume
          COMMENT 'Contratos com maior volume de transações por hora'
          AS
          SELECT
            to_address                               AS contract_address,
            COUNT(*)                                 AS tx_count,
            SUM(CAST(value AS DOUBLE))               AS total_value_wei,
            DATE_TRUNC('hour', _ingested_at)         AS hour_bucket
          FROM `{cat}`.s_apps.transactions_fast
          WHERE to_address IS NOT NULL
          GROUP BY to_address, DATE_TRUNC('hour', _ingested_at)
        """)
        _log.info("View ensured: %s.gold.top_contracts_by_volume", cat)

        self.spark.sql(f"""
          CREATE OR REPLACE VIEW `{cat}`.gold.blocks_hourly_summary
          COMMENT 'Resumo horário de blocos: contagem, gás médio e taxa base média'
          AS
          SELECT
            DATE_TRUNC('hour', block_time) AS hour_bucket,
            COUNT(*)                        AS block_count,
            AVG(transaction_count)          AS avg_tx_per_block,
            AVG(gas_used)                   AS avg_gas_used,
            AVG(base_fee_per_gas)           AS avg_base_fee
          FROM `{cat}`.s_apps.blocks_fast
          GROUP BY DATE_TRUNC('hour', block_time)
        """)
        _log.info("View ensured: %s.gold.blocks_hourly_summary", cat)

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
