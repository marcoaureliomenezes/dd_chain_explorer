"""setup_ddl.py — DDL para DD Chain Explorer Unity Catalog.

Fonte única de verdade para todos os schemas e tabelas do projeto.
Deve ser executado ANTES dos pipelines DLT.

Enforcement de schema:
  Este script pré-cria todas as tabelas com schema explícito e COMMENT por coluna.
  O DLT escreve nas tabelas pré-existentes; qualquer mismatch de schema → DLT FALHA.
  Para enforcement completo de "fail se tabela não existir", revogue o privilégio
  CREATE TABLE do service principal DLT no Unity Catalog:
    REVOKE CREATE TABLE ON SCHEMA <cat>.<schema> FROM `<dlt-principal>`;

Tabelas EXTERNAL (dados em S3 independente do Databricks):
  - DLT Serverless NÃO suporta LOCATION (limitação Databricks). Para EXTERNAL em DLT,
    desabilite serverless: false e adicione path= no decorador @dlt.table().
  - Jobs batch (não-DLT) podem usar EXTERNAL com LOCATION → registre em EXTERNAL_TABLES.

Flags:
  --catalog               Catálogo Unity Catalog (obrigatório)
  --lakehouse-s3-bucket   Bucket S3 para tabelas EXTERNAL batch (obrigatório)
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
    DDL idempotente e fonte única de verdade para o catálogo DD Chain Explorer.

    Fluxo esperado (DABs workflow ordering):
      Step 1: dm-ddl-setup  → DDChainExplorerDDL.setup_all()  (este script)
      Step 2: dm-ethereum   → DLT pipeline (tabelas já existem, schema validado)
      Step 3: dm-app-logs   → DLT pipeline (tabelas já existem, schema validado)

    Schema enforcement:
      DLT escreve nas tabelas pré-existentes. Se o DataFrame não bater com o
      schema aqui definido, o DLT falha — esse é o mecanismo de enforcement.
    """

    ALL_SCHEMAS = ("b_ethereum", "b_app_logs", "s_apps", "s_logs", "g_apps", "g_network", "g_api_keys")

    # Tabelas EXTERNAL gerenciadas por jobs batch (não-DLT).
    # Formato: {"schema.table": "s3-relative-path"}
    # Usado por drop_all() para remover dados S3 antes do DROP SCHEMA CASCADE.
    EXTERNAL_TABLES: dict[str, str] = {
        # "s_apps.transactions_batch": "s_apps/transactions_batch",
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
        """Criação idempotente: schemas + todas as tabelas (DLT e batch EXTERNAL)."""
        self._create_schemas()
        self._create_bronze_ethereum_tables()
        self._create_bronze_app_logs_tables()
        self._create_silver_apps_tables()
        self._create_silver_logs_tables()
        self._create_gold_apps_tables()
        self._create_gold_network_tables()
        self._create_gold_api_keys_tables()
        self._create_external_batch_tables()
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
    # Bronze — b_ethereum  (pipeline dm-ethereum, Auto Loader via Firehose)
    # ------------------------------------------------------------------

    def _create_bronze_ethereum_tables(self) -> None:
        cat = self.catalog
        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.b_blocks_data (
            number           BIGINT   COMMENT 'Número do bloco na mainnet Ethereum',
            hash             STRING   COMMENT 'Hash do bloco (0x..., 66 chars)',
            parentHash       STRING   COMMENT 'Hash do bloco pai',
            timestamp        BIGINT   COMMENT 'Unix timestamp do bloco (segundos epoch)',
            miner            STRING   COMMENT 'Endereço do minerador/validator',
            difficulty       STRING   COMMENT 'Dificuldade de mineração (string 256-bit)',
            totalDifficulty  STRING   COMMENT 'Dificuldade acumulada até este bloco',
            nonce            STRING   COMMENT 'Nonce do bloco (pós-merge = 0x0000000000000000)',
            size             BIGINT   COMMENT 'Tamanho do bloco serializado em bytes',
            baseFeePerGas    STRING   COMMENT 'EIP-1559: taxa base por gas em Wei',
            gasLimit         BIGINT   COMMENT 'Gas limit máximo permitido no bloco',
            gasUsed          BIGINT   COMMENT 'Gas total consumido por todas as transações',
            logsBloom        STRING   COMMENT 'Bloom filter dos logs do bloco (2048 bits)',
            extraData        STRING   COMMENT 'Campo extra do bloco definido pelo minerador (hex)',
            transactionsRoot STRING   COMMENT 'Raiz da Merkle trie de transações',
            stateRoot        STRING   COMMENT 'Raiz da Merkle trie de estado pós-bloco',
            transactions     ARRAY<STRING> COMMENT 'Hashes das transações incluídas no bloco',
            withdrawals      ARRAY<STRUCT<index: BIGINT, validatorIndex: BIGINT, address: STRING, amount: BIGINT>>
                                      COMMENT 'Saques ETH da Beacon Chain (EIP-4895, pós-Shanghai)',
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)'
          )
          COMMENT 'Bronze: dados brutos de blocos Ethereum — Firehose mainnet-blocks-data → S3 → Auto Loader.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_ethereum.b_blocks_data", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.b_transactions_data (
            hash             STRING   COMMENT 'Hash único da transação (0x..., 66 chars)',
            blockNumber      BIGINT   COMMENT 'Número do bloco que contém esta transação',
            blockHash        STRING   COMMENT 'Hash do bloco que contém esta transação',
            transactionIndex BIGINT   COMMENT 'Índice 0-based da transação dentro do bloco',
            `from`           STRING   COMMENT 'Endereço EOA originador (0x...)',
            to               STRING   COMMENT 'Endereço de destino — contrato ou EOA (nulo em deploy)',
            value            STRING   COMMENT 'Valor em Wei como string (256-bit precision)',
            input            STRING   COMMENT 'Calldata hex (seletor 4 bytes + ABI-encoded params)',
            gas              STRING   COMMENT 'Gas limit definido pelo remetente',
            gasPrice         STRING   COMMENT 'Gas price em Wei (legacy ou EIP-1559 max_fee)',
            nonce            BIGINT   COMMENT 'Nonce da conta remetente',
            v                STRING   COMMENT 'Componente V da assinatura ECDSA',
            r                STRING   COMMENT 'Componente R da assinatura ECDSA',
            s                STRING   COMMENT 'Componente S da assinatura ECDSA',
            type             STRING   COMMENT 'Tipo EIP-2718 (0=legacy, 1=access-list, 2=dynamic-fee)',
            accessList       ARRAY<STRING> COMMENT 'Access list EIP-2930 (storage pre-warming)',
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)'
          )
          COMMENT 'Bronze: dados brutos de transações Ethereum — Firehose mainnet-transactions-data → S3 → Auto Loader.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_ethereum.b_transactions_data", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.b_transactions_decoded (
            tx_hash          STRING   COMMENT 'Hash da transação cujo input foi decodificado',
            contract_address STRING   COMMENT 'Endereço do contrato chamado',
            method           STRING   COMMENT 'Nome do método ABI (ex: transfer, swap)',
            parms            STRING   COMMENT 'Parâmetros ABI-decoded como JSON string',
            decode_type      STRING   COMMENT 'Estratégia usada: abi | 4byte | unknown',
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)'
          )
          COMMENT 'Bronze: inputs de transações decodificados — Firehose mainnet-transactions-decoded → S3 → Auto Loader.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_ethereum.b_transactions_decoded", cat)

    # ------------------------------------------------------------------
    # Bronze — b_app_logs  (pipeline dm-app-logs, CloudWatch → Firehose → S3)
    # ------------------------------------------------------------------

    def _create_bronze_app_logs_tables(self) -> None:
        cat = self.catalog
        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_app_logs.b_app_logs_data (
            timestamp      BIGINT    COMMENT 'Timestamp do evento em milissegundos epoch (CloudWatch)',
            logger         STRING    COMMENT 'Nome da aplicação que gerou o log',
            level          STRING    COMMENT 'Nível do log (INFO, WARNING, ERROR, DEBUG)',
            filename       STRING    COMMENT 'Arquivo Python que emitiu o log',
            function_name  STRING    COMMENT 'Função Python que emitiu o log',
            message        STRING    COMMENT 'Mensagem de log (texto livre ou JSON estruturado)',
            log_group      STRING    COMMENT 'CloudWatch Log Group de origem',
            log_stream     STRING    COMMENT 'CloudWatch Log Stream de origem',
            _ingested_at   TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)'
          )
          COMMENT 'Bronze: logs das aplicações on-chain — CloudWatch → Firehose → S3 (double-gzip NDJSON).'
          USING DELTA
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_app_logs.b_app_logs_data", cat)

    # ------------------------------------------------------------------
    # Silver — s_apps  (pipeline dm-ethereum)
    # ------------------------------------------------------------------

    def _create_silver_apps_tables(self) -> None:
        cat = self.catalog

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.blocks_fast (
            block_number      BIGINT   COMMENT 'Número do bloco Ethereum',
            block_hash        STRING   COMMENT 'Hash único do bloco (0x...)',
            parent_hash       STRING   COMMENT 'Hash do bloco pai',
            block_time        TIMESTAMP COMMENT 'Timestamp do bloco convertido para TIMESTAMP',
            block_timestamp   BIGINT   COMMENT 'Unix timestamp original do bloco (segundos epoch)',
            miner             STRING   COMMENT 'Endereço do validator/minerador',
            difficulty        STRING   COMMENT 'Dificuldade de mineração (string 256-bit)',
            total_difficulty  STRING   COMMENT 'Dificuldade acumulada até este bloco',
            nonce             STRING   COMMENT 'Nonce do bloco',
            size              BIGINT   COMMENT 'Tamanho do bloco em bytes',
            base_fee_per_gas  STRING   COMMENT 'EIP-1559: taxa base por gas em Wei',
            gas_limit         BIGINT   COMMENT 'Gas limit máximo do bloco',
            gas_used          BIGINT   COMMENT 'Gas total consumido no bloco',
            logs_bloom        STRING   COMMENT 'Bloom filter para consulta de logs (2048 bits)',
            extra_data        STRING   COMMENT 'Dados extra do bloco (hex, máx 32 bytes)',
            transactions_root STRING   COMMENT 'Raiz da Merkle trie de transações',
            state_root        STRING   COMMENT 'Raiz da Merkle trie de estado pós-bloco',
            transaction_count INT      COMMENT 'Número de transações no bloco',
            transactions      ARRAY<STRING> COMMENT 'Hashes das transações do bloco',
            withdrawals       ARRAY<STRUCT<index: BIGINT, validatorIndex: BIGINT, address: STRING, amount: BIGINT>>
                                       COMMENT 'Saques ETH da Beacon Chain (EIP-4895)',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão original'
          )
          COMMENT 'Silver: blocos Ethereum completos — limpeza e tipagem de b_ethereum.b_blocks_data.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.blocks_fast", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_fast (
            tx_hash           STRING   COMMENT 'Hash único da transação Ethereum (0x...)',
            block_number      BIGINT   COMMENT 'Número do bloco que contém a transação',
            block_hash        STRING   COMMENT 'Hash do bloco que contém a transação',
            transaction_index BIGINT   COMMENT 'Índice 0-based da transação no bloco',
            from_address      STRING   COMMENT 'Endereço EOA remetente (0x...)',
            to_address        STRING   COMMENT 'Endereço de destino (nulo em deploys de contrato)',
            value             STRING   COMMENT 'Valor em Wei (string 256-bit precision)',
            input             STRING   COMMENT 'Calldata hex da transação',
            gas               STRING   COMMENT 'Gas limit da transação',
            gas_price         STRING   COMMENT 'Gas price em Wei',
            nonce             BIGINT   COMMENT 'Nonce da conta remetente',
            v                 STRING   COMMENT 'Componente V da assinatura ECDSA',
            r                 STRING   COMMENT 'Componente R da assinatura ECDSA',
            s                 STRING   COMMENT 'Componente S da assinatura ECDSA',
            tx_type           STRING   COMMENT 'Tipo de transação EIP-2718',
            access_list       ARRAY<STRING> COMMENT 'Access list EIP-2930',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão original',
            event_date        DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Silver: transações Ethereum raw sem input decodificado.'
          USING DELTA
          PARTITIONED BY (event_date)
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.transactions_fast", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.txs_inputs_decoded_fast (
            tx_hash          STRING   COMMENT 'Hash da transação cujo input foi decodificado',
            contract_address STRING   COMMENT 'Endereço do contrato chamado',
            method           STRING   COMMENT 'Nome do método ABI (ex: transfer, swapExactTokensForTokens)',
            parms            STRING   COMMENT 'Parâmetros ABI-decoded como JSON string',
            decode_type      STRING   COMMENT 'Estratégia: abi | 4byte | unknown',
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão original'
          )
          COMMENT 'Silver: inputs de transações decodificados — limpeza de b_ethereum.b_transactions_decoded.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.txs_inputs_decoded_fast", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_ethereum (
            tx_hash           STRING   COMMENT 'Hash único da transação Ethereum',
            block_number      BIGINT   COMMENT 'Número do bloco',
            block_hash        STRING   COMMENT 'Hash do bloco',
            transaction_index BIGINT   COMMENT 'Posição 0-based da transação no bloco',
            from_address      STRING   COMMENT 'Endereço EOA remetente',
            to_address        STRING   COMMENT 'Endereço de destino (nulo em deploys)',
            value             STRING   COMMENT 'Valor em Wei (string 256-bit)',
            input             STRING   COMMENT 'Calldata hex da transação',
            gas               STRING   COMMENT 'Gas limit da transação',
            gas_price         STRING   COMMENT 'Gas price em Wei',
            nonce             BIGINT   COMMENT 'Nonce do remetente',
            tx_type           STRING   COMMENT 'Tipo de transação EIP-2718',
            tx_timestamp      STRING   COMMENT 'Timestamp da transação derivado do bloco (yyyy-MM-dd HH:mm:ss)',
            block_gas_limit   BIGINT   COMMENT 'Gas limit do bloco',
            block_gas_used    BIGINT   COMMENT 'Gas total usado no bloco',
            base_fee_per_gas  STRING   COMMENT 'EIP-1559: taxa base do bloco em Wei',
            contract_address  STRING   COMMENT 'Endereço do contrato chamado (do decoder, nullable)',
            method            STRING   COMMENT 'Método ABI decodificado (nullable)',
            parms             STRING   COMMENT 'Parâmetros ABI-decoded como JSON (nullable)',
            decode_type       STRING   COMMENT 'Estratégia de decodificação (nullable)',
            input_etherscan   STRING   COMMENT 'Input via Etherscan API — enriquecimento batch (nullable)',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão original',
            event_date        DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Silver: transações Ethereum enriquecidas — JOIN streaming + decoded inputs + dados do bloco.'
          USING DELTA
          PARTITIONED BY (event_date)
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.transactions_ethereum", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.blocks_withdrawals (
            block_number       BIGINT   COMMENT 'Número do bloco Ethereum',
            block_timestamp    STRING   COMMENT 'Timestamp do bloco formatado (yyyy-MM-dd HH:mm:ss)',
            miner              STRING   COMMENT 'Endereço do validator/minerador do bloco',
            withdrawal_index   BIGINT   COMMENT 'Índice global do saque na Beacon Chain',
            validator_index    BIGINT   COMMENT 'Índice do validator que realizou o saque',
            withdrawal_address STRING   COMMENT 'Endereço de destino do ETH sacado (0x...)',
            amount_gwei        BIGINT   COMMENT 'Valor do saque em Gwei (1 ETH = 1e9 Gwei)',
            amount_eth         DOUBLE   COMMENT 'Valor do saque em ETH (amount_gwei / 1e9)',
            _ingested_at       TIMESTAMP COMMENT 'Timestamp de ingestão original'
          )
          COMMENT 'Silver: saques ETH da Beacon Chain (EIP-4895/Shanghai) — uma linha por withdrawal por bloco.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.blocks_withdrawals", cat)

    # ------------------------------------------------------------------
    # Silver — s_logs  (pipeline dm-app-logs)
    # ------------------------------------------------------------------

    def _create_silver_logs_tables(self) -> None:
        cat = self.catalog
        _LOGS_SCHEMA = """
            event_ts_epoch  BIGINT    COMMENT 'Timestamp do evento em milissegundos epoch (CloudWatch)',
            event_time      TIMESTAMP COMMENT 'Timestamp do evento convertido para TIMESTAMP',
            logger          STRING    COMMENT 'Nome da aplicação que gerou o log',
            level           STRING    COMMENT 'Nível do log (INFO, WARNING, ERROR, DEBUG)',
            filename        STRING    COMMENT 'Arquivo Python que emitiu o log',
            function_name   STRING    COMMENT 'Função Python que emitiu o log',
            message         STRING    COMMENT 'Mensagem de log',
            _ingested_at    TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader'
        """
        for name, apps in [
            ("logs_streaming", "MINED_BLOCKS_EVENTS, ORPHAN_BLOCKS_CRAWLER, BLOCK_DATA_CRAWLER, RAW_TXS_CRAWLER, TRANSACTION_INPUT_DECODER"),
            ("logs_batch",     "CONTRACT_TRANSACTIONS_CRAWLER"),
        ]:
            self._sql(f"""
              CREATE TABLE IF NOT EXISTS `{cat}`.s_logs.{name} ({_LOGS_SCHEMA})
              COMMENT 'Silver: logs das aplicações de {name.split('_')[1]} on-chain ({apps}).'
              USING DELTA
              TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
            """)
            _log.info("Table ensured: %s.s_logs.%s", cat, name)

    # ------------------------------------------------------------------
    # Gold — g_apps  (pipeline dm-ethereum, Materialized Views)
    # ------------------------------------------------------------------

    def _create_gold_apps_tables(self) -> None:
        cat = self.catalog

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.popular_contracts_ranking (
            contract_address STRING    COMMENT 'Endereço do contrato inteligente (0x...)',
            tx_count         BIGINT    COMMENT 'Total de transações recebidas na última hora',
            unique_senders   BIGINT    COMMENT 'Número de EOAs distintos que interagiram',
            first_seen       TIMESTAMP COMMENT 'Timestamp da primeira transação na janela de 1h',
            last_seen        TIMESTAMP COMMENT 'Timestamp da última transação na janela de 1h',
            computed_at      TIMESTAMP COMMENT 'Timestamp de computação desta Materialized View'
          )
          COMMENT 'Gold MV: top 100 contratos Ethereum por volume de transações na última hora. Fonte para o job batch Etherscan.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.popular_contracts_ranking", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.peer_to_peer_txs (
            tx_hash          STRING    COMMENT 'Hash único da transação',
            block_number     BIGINT    COMMENT 'Número do bloco',
            from_address     STRING    COMMENT 'Endereço EOA remetente',
            to_address       STRING    COMMENT 'Endereço EOA destinatário',
            value            STRING    COMMENT 'Valor em Wei',
            gas              STRING    COMMENT 'Gas limit da transação',
            gas_price        STRING    COMMENT 'Gas price em Wei',
            tx_timestamp     STRING    COMMENT 'Timestamp da transação (yyyy-MM-dd HH:mm:ss)',
            base_fee_per_gas STRING    COMMENT 'EIP-1559: taxa base do bloco em Wei',
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão original'
          )
          COMMENT 'Gold MV: transferências ETH diretas entre EOAs (input vazio/0x, to_address não nulo).'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.peer_to_peer_txs", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.ethereum_gas_consume (
            block_number         BIGINT   COMMENT 'Número do bloco',
            tx_hash              STRING   COMMENT 'Hash único da transação',
            from_address         STRING   COMMENT 'Endereço EOA remetente',
            to_address           STRING   COMMENT 'Endereço de destino (nullable em deploys)',
            value                STRING   COMMENT 'Valor em Wei',
            gas_price            STRING   COMMENT 'Gas price em Wei',
            gas_limit            STRING   COMMENT 'Gas limit da transação (campo gas)',
            tx_timestamp         STRING   COMMENT 'Timestamp da transação derivado do bloco',
            type_transaction     STRING   COMMENT 'peer_to_peer | contract_interaction | contract_deploy',
            block_gas_limit      BIGINT   COMMENT 'Gas limit do bloco',
            block_gas_used       BIGINT   COMMENT 'Gas total usado no bloco',
            gas_pct_of_block     DOUBLE   COMMENT 'Percentual do block_gas_used consumido por esta tx (gas_limit/block_gas_used × 100)',
            base_fee_per_gas     STRING   COMMENT 'EIP-1559: taxa base do bloco em Wei'
          )
          COMMENT 'Gold MV: consumo de gas por transação com classificação de tipo.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.ethereum_gas_consume", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.transactions_lambda (
            tx_hash          STRING   COMMENT 'Hash único da transação',
            block_number     BIGINT   COMMENT 'Número do bloco',
            from_address     STRING   COMMENT 'Endereço EOA remetente',
            contract_address STRING   COMMENT 'Endereço do contrato (to_address dos contratos populares)',
            value            STRING   COMMENT 'Valor em Wei',
            gas              STRING   COMMENT 'Gas limit da transação',
            gas_price        STRING   COMMENT 'Gas price em Wei',
            input            STRING   COMMENT 'Calldata hex da transação',
            method           STRING   COMMENT 'Método ABI decodificado (streaming)',
            parms            STRING   COMMENT 'Parâmetros ABI-decoded como JSON',
            decode_type      STRING   COMMENT 'Estratégia de decodificação: abi | 4byte | unknown',
            input_etherscan  STRING   COMMENT 'Input via Etherscan API (enriquecimento batch)',
            event_time       STRING   COMMENT 'Timestamp da transação (yyyy-MM-dd HH:mm:ss)'
          )
          COMMENT 'Gold MV: arquitetura Lambda — transações dos contratos populares com input decodificado (streaming + batch Etherscan).'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.transactions_lambda", cat)

    # ------------------------------------------------------------------
    # Gold — g_network  (pipeline dm-ethereum)
    # ------------------------------------------------------------------

    def _create_gold_network_tables(self) -> None:
        cat = self.catalog
        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_network.network_metrics_hourly (
            hour_bucket                TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            block_count                BIGINT    COMMENT 'Blocos produzidos na hora',
            tx_count                   BIGINT    COMMENT 'Transações processadas na hora',
            tps_avg                    DOUBLE    COMMENT 'TPS médio (tx_count / 3600 s)',
            avg_gas_price_gwei         DOUBLE    COMMENT 'Gas price médio em Gwei',
            avg_block_gas_used         DOUBLE    COMMENT 'Gas médio consumido por bloco',
            avg_block_gas_limit        DOUBLE    COMMENT 'Gas limit médio por bloco',
            avg_block_utilization_pct  DOUBLE    COMMENT 'Utilização média dos blocos (gas_used/gas_limit × 100)',
            avg_txs_per_block          DOUBLE    COMMENT 'Média de transações por bloco',
            computed_at                TIMESTAMP COMMENT 'Timestamp de computação desta Materialized View'
          )
          COMMENT 'Gold MV: métricas horárias da rede Ethereum — TPS, gas, utilização de blocos e volume.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.network_metrics_hourly", cat)

    # ------------------------------------------------------------------
    # Gold — g_api_keys  (pipeline dm-app-logs)
    # ------------------------------------------------------------------

    def _create_gold_api_keys_tables(self) -> None:
        cat = self.catalog
        _KEYS_WINDOWS = """
            calls_total       BIGINT    COMMENT 'Total de chamadas acumuladas',
            calls_ok_total    BIGINT    COMMENT 'Total de chamadas com status ok',
            calls_error_total BIGINT    COMMENT 'Total de chamadas com erro',
            calls_1h          BIGINT    COMMENT 'Chamadas na última 1 hora',
            calls_2h          BIGINT    COMMENT 'Chamadas nas últimas 2 horas',
            calls_12h         BIGINT    COMMENT 'Chamadas nas últimas 12 horas',
            calls_24h         BIGINT    COMMENT 'Chamadas nas últimas 24 horas',
            calls_48h         BIGINT    COMMENT 'Chamadas nas últimas 48 horas',
            last_call_at      TIMESTAMP COMMENT 'Timestamp da última chamada registrada',
            computed_at       TIMESTAMP COMMENT 'Timestamp de computação desta Materialized View'
        """
        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_api_keys.etherscan_consumption (
            api_key_name STRING COMMENT 'Nome da API key Etherscan (identificador SSM)',
            {_KEYS_WINDOWS}
          )
          COMMENT 'Gold MV: consumo de API keys Etherscan por janela de tempo — monitoramento de rate limits.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_api_keys.etherscan_consumption", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_api_keys.web3_keys_consumption (
            api_key_name STRING COMMENT 'Nome da API key Web3 (identificador SSM)',
            vendor       STRING COMMENT 'Provedor Web3: alchemy | infura | unknown',
            {_KEYS_WINDOWS}
          )
          COMMENT 'Gold MV: consumo de API keys Web3 (Alchemy/Infura) por janela de tempo.'
          USING DELTA
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_api_keys.web3_keys_consumption", cat)

    # ------------------------------------------------------------------
    # EXTERNAL batch tables (jobs não-DLT — dados diretamente em S3)
    # ------------------------------------------------------------------

    def _create_external_batch_tables(self) -> None:
        """Cria tabelas EXTERNAL gerenciadas por jobs batch (não pelo DLT).
        Adicione entradas em EXTERNAL_TABLES e o CREATE TABLE correspondente abaixo.
        """
        cat = self.catalog
        bucket = self.lakehouse_bucket
        # Exemplo de tabela batch EXTERNAL (descomentar e adicionar DDL quando necessário):
        # self._sql(f'''
        #   CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_batch (
        #     ...
        #   )
        #   USING DELTA
        #   LOCATION 's3://{bucket}/s_apps/transactions_batch'
        #   TBLPROPERTIES ('quality' = 'silver')
        # ''')
        _ = (cat, bucket)  # suprime warnings de variáveis não usadas


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
    args = parser.parse_args()  # type: ignore[attr-defined]

    ddl = DDChainExplorerDDL(args.catalog, args.lakehouse_s3_bucket)

    if args.drop:
        ddl.drop_all()

    ddl.setup_all()


if __name__ == "__main__":
    main()
