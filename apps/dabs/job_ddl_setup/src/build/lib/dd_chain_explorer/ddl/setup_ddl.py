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
        # Serverless python_wheel_task não injeta 'spark' como global no módulo do wheel.
        # SparkSession.builder.getOrCreate() recupera a sessão já ativa no kernel.
        from pyspark.sql import SparkSession
        self._spark = SparkSession.builder.getOrCreate()

    def _sql(self, statement: str) -> None:
        _log.debug("SQL: %s", statement[:120].replace("\n", " "))
        self._spark.sql(statement)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def drop_all(self) -> None:
        """Remove dados S3 das tabelas EXTERNAL + DROP SCHEMA CASCADE."""
        from pyspark.dbutils import DBUtils
        _dbutils = DBUtils(self._spark)
        cat = self.catalog
        for rel_path in self.EXTERNAL_TABLES.values():
            location = f"s3://{self.lakehouse_bucket}/{rel_path}"
            try:
                _dbutils.fs.rm(location, recurse=True)
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
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.eth_mined_blocks (
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
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)',
            dat_ref          DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Bronze: dados brutos de blocos Ethereum — Firehose mainnet-blocks-data → S3 → Auto Loader.'
          PARTITIONED BY (dat_ref)
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_ethereum.eth_mined_blocks", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.eth_transactions (
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
            _ingested_at     TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)',
            dat_ref          DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Bronze: dados brutos de transações Ethereum — Firehose mainnet-transactions-data → S3 → Auto Loader.'
          PARTITIONED BY (dat_ref)
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_ethereum.eth_transactions", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.eth_txs_input_decoded (
            tx_hash           STRING   COMMENT 'Hash da transação cujo input foi decodificado',
            contract_address  STRING   COMMENT 'Endereço do contrato chamado',
            method            STRING   COMMENT 'Nome do método ABI (ex: transfer, swap)',
            parms             STRING   COMMENT 'Parâmetros ABI-decoded como JSON string',
            method_id         STRING   COMMENT 'Seletor 4-byte hex do método (ex: 0xa9059cbb)',
            decode_type       STRING   COMMENT 'Estratégia de decodificação: abi | 4byte | unknown',
            decode_source     STRING   COMMENT 'Fonte da decodificação: abi_cache | etherscan_api | 4byte_directory | unknown',
            decode_confidence STRING   COMMENT 'Confiança do decode: full (params completos) | partial (método só) | none',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão pelo Auto Loader (UTC)',
            dat_ref           DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Bronze: inputs de transações decodificados — Firehose mainnet-transactions-decoded → S3 → Auto Loader.'
          PARTITIONED BY (dat_ref)
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_ethereum.eth_txs_input_decoded", cat)

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
          TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.b_app_logs.b_app_logs_data", cat)

    # ------------------------------------------------------------------
    # Silver — s_apps  (pipeline dm-ethereum)
    # ------------------------------------------------------------------

    def _create_silver_apps_tables(self) -> None:
        cat = self.catalog

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.eth_blocks (
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
          COMMENT 'Silver: blocos Ethereum completos — limpeza e tipagem de b_ethereum.eth_mined_blocks.'
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.eth_blocks", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.eth_transactions_staging (
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
            v                 STRING   COMMENT 'Componente V da assinatura ECDSA (staging only)',
            r                 STRING   COMMENT 'Componente R da assinatura ECDSA (staging only)',
            s                 STRING   COMMENT 'Componente S da assinatura ECDSA (staging only)',
            tx_type           STRING   COMMENT 'Tipo de transação EIP-2718',
            access_list       ARRAY<STRING> COMMENT 'Access list EIP-2930',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão original',
            dat_ref           DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Silver staging: transações Ethereum raw — tabela interna DLT, não consultar diretamente. Use s_apps.transactions_ethereum.'
          PARTITIONED BY (dat_ref)
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.eth_transactions_staging", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.txs_inputs_decoded_fast (
            tx_hash           STRING   COMMENT 'Hash da transação cujo input foi decodificado',
            contract_address  STRING   COMMENT 'Endereço do contrato chamado',
            method            STRING   COMMENT 'Nome do método ABI (ex: transfer, swapExactTokensForTokens)',
            parms             STRING   COMMENT 'Parâmetros ABI-decoded como JSON string',
            method_id         STRING   COMMENT 'Seletor 4-byte hex do método (ex: 0xa9059cbb)',
            decode_type       STRING   COMMENT 'Estratégia: abi | 4byte | unknown',
            decode_source     STRING   COMMENT 'Fonte: abi_cache | etherscan_api | 4byte_directory | unknown',
            decode_confidence STRING   COMMENT 'Confiança: full | partial | none',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão original'
          )
          COMMENT 'Silver: inputs de transações decodificados — limpeza de b_ethereum.eth_txs_input_decoded.'
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
            tx_type_semantic  STRING   COMMENT 'Tipo semântico: peer_to_peer | contract_interaction | contract_deploy',
            tx_timestamp      STRING   COMMENT 'Timestamp da transação derivado do bloco (yyyy-MM-dd HH:mm:ss)',
            block_gas_limit   BIGINT   COMMENT 'Gas limit do bloco',
            block_gas_used    BIGINT   COMMENT 'Gas total usado no bloco',
            base_fee_per_gas  STRING   COMMENT 'EIP-1559: taxa base do bloco em Wei',
            contract_address  STRING   COMMENT 'Endereço do contrato chamado (do decoder, nullable)',
            method            STRING   COMMENT 'Método ABI decodificado (nullable)',
            parms             STRING   COMMENT 'Parâmetros ABI-decoded como JSON (nullable)',
            method_id         STRING   COMMENT 'Seletor 4-byte hex (ex: 0xa9059cbb, nullable)',
            decode_type       STRING   COMMENT 'Estratégia de decodificação: abi | 4byte | unknown (nullable)',
            decode_source     STRING   COMMENT 'Fonte do decode: abi_cache | etherscan_api | 4byte_directory | unknown (nullable)',
            decode_confidence STRING   COMMENT 'Confiança do decode: full | partial | none (nullable)',
            tx_status         STRING   COMMENT 'Status de canonicidade: valid | orphaned | unconfirmed',
            receipt_status    BIGINT   COMMENT 'Status do receipt Etherscan: 1=sucesso, 0=revertido (nullable, batch only)',
            is_error          BIGINT   COMMENT 'Flag de erro Etherscan: 0=ok, 1=erro (nullable, batch only)',
            _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão original',
            dat_ref           DATE     COMMENT 'Data de ingestão — chave de partição Delta'
          )
          COMMENT 'Silver: transações Ethereum enriquecidas — JOIN streaming + decoded inputs + dados do bloco. tx_status = valid|orphaned|unconfirmed.'
          PARTITIONED BY (dat_ref)
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.transactions_ethereum", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.eth_blocks_withdrawals (
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
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.eth_blocks_withdrawals", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.eth_canonical_blocks_index (
            block_number  BIGINT  COMMENT 'Número do bloco Ethereum',
            block_hash    STRING  COMMENT 'Hash do bloco (0x...)',
            chain_status  STRING  COMMENT 'Status na cadeia canônica: canonical | orphan | unconfirmed'
          )
          COMMENT 'Silver: índice de status de blocos derivado de parentHash. Recomputado integralmente a cada pipeline update.'
          TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.s_apps.eth_canonical_blocks_index", cat)

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
            tx_type_semantic     STRING   COMMENT 'Tipo semântico: peer_to_peer | contract_interaction | contract_deploy',
            block_gas_limit      BIGINT   COMMENT 'Gas limit do bloco',
            block_gas_used       BIGINT   COMMENT 'Gas total usado no bloco',
            gas_pct_of_block     DOUBLE   COMMENT 'Percentual do block_gas_used consumido por esta tx (gas_limit/block_gas_used × 100)',
            base_fee_per_gas     STRING   COMMENT 'EIP-1559: taxa base do bloco em Wei'
          )
          COMMENT 'Gold MV: consumo de gas por transação com classificação de tipo semântico.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.ethereum_gas_consume", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.transactions_lambda (
            tx_hash           STRING   COMMENT 'Hash único da transação',
            block_number      BIGINT   COMMENT 'Número do bloco',
            from_address      STRING   COMMENT 'Endereço EOA remetente',
            contract_address  STRING   COMMENT 'Endereço do contrato (to_address dos contratos populares)',
            value             STRING   COMMENT 'Valor em Wei',
            gas               STRING   COMMENT 'Gas limit da transação',
            gas_price         STRING   COMMENT 'Gas price em Wei',
            input             STRING   COMMENT 'Calldata hex da transação',
            method            STRING   COMMENT 'Método ABI decodificado (streaming)',
            parms             STRING   COMMENT 'Parâmetros ABI-decoded como JSON',
            method_id         STRING   COMMENT 'Seletor 4-byte hex (ex: 0xa9059cbb)',
            decode_type       STRING   COMMENT 'Estratégia de decodificação: abi | 4byte | unknown',
            decode_source     STRING   COMMENT 'Fonte do decode: abi_cache | etherscan_api | 4byte_directory | unknown',
            decode_confidence STRING   COMMENT 'Confiança do decode: full | partial | none',
            tx_type_semantic  STRING   COMMENT 'Tipo semântico: peer_to_peer | contract_interaction | contract_deploy',
            tx_status         STRING   COMMENT 'Status de canonicidade: valid | unconfirmed',
            event_time        STRING   COMMENT 'Timestamp da transação (yyyy-MM-dd HH:mm:ss)'
          )
          COMMENT 'Gold MV: arquitetura Lambda — transações dos contratos populares com input decodificado (streaming + batch Etherscan).'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.transactions_lambda", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.gas_price_distribution_hourly (
            hour_bucket          TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            tx_type_semantic     STRING    COMMENT 'Tipo semântico da transação (peer_to_peer | contract_interaction | contract_deploy)',
            tx_count             BIGINT    COMMENT 'Total de transações na hora+tipo',
            gas_price_p25_gwei   DOUBLE    COMMENT 'Percentil 25 do gas_price em Gwei',
            gas_price_p50_gwei   DOUBLE    COMMENT 'Percentil 50 (mediana) do gas_price em Gwei',
            gas_price_p75_gwei   DOUBLE    COMMENT 'Percentil 75 do gas_price em Gwei',
            gas_price_p95_gwei   DOUBLE    COMMENT 'Percentil 95 do gas_price em Gwei',
            gas_price_avg_gwei   DOUBLE    COMMENT 'Média do gas_price em Gwei',
            computed_at          TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV (UC2): distribuição de gas_price por tipo de transação por hora.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.gas_price_distribution_hourly", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.p2p_transfer_metrics_hourly (
            hour_bucket           TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            tx_count              BIGINT    COMMENT 'Número de transferências P2P na hora',
            unique_senders        BIGINT    COMMENT 'Endereços EOA únicos que enviaram na hora',
            unique_receivers      BIGINT    COMMENT 'Endereços EOA únicos que receberam na hora',
            total_eth_transferred DOUBLE    COMMENT 'Volume total de ETH transferido (Wei ÷ 1e18)',
            avg_eth_per_tx        DOUBLE    COMMENT 'Média de ETH por transferência',
            max_eth_per_tx        DOUBLE    COMMENT 'Maior transferência individual em ETH',
            computed_at           TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV (UC3): métricas horárias de transferências ETH P2P (peer_to_peer).'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.p2p_transfer_metrics_hourly", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.contract_method_activity (
            contract_address  STRING    COMMENT 'Endereço do contrato inteligente',
            method            STRING    COMMENT 'Nome do método ABI chamado',
            method_id         STRING    COMMENT 'Seletor 4-byte hex do método',
            decode_type       STRING    COMMENT 'Fonte da decodificação (abi | 4byte | unknown)',
            call_count        BIGINT    COMMENT 'Número de chamadas na janela (24h)',
            unique_callers    BIGINT    COMMENT 'EOAs únicos que chamaram este método',
            first_seen        TIMESTAMP COMMENT 'Primeira chamada registrada na janela',
            last_seen         TIMESTAMP COMMENT 'Última chamada registrada na janela',
            computed_at       TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV (UC4): ranking de métodos chamados por contrato nas últimas 24h (TOP 50).'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.contract_method_activity", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.contract_deploy_metrics_hourly (
            hour_bucket        TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            deploy_count       BIGINT    COMMENT 'Número de deploys de contrato na hora',
            unique_deployers   BIGINT    COMMENT 'EOAs distintos que fizeram deploy na hora',
            avg_gas_price_gwei DOUBLE    COMMENT 'Gas price médio dos deploys em Gwei',
            computed_at        TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV (UC5): métricas horárias de deploys de contratos Ethereum.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.contract_deploy_metrics_hourly", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_apps.contract_volume_ranking (
            contract_address      STRING    COMMENT 'Endereço do contrato inteligente',
            tx_count              BIGINT    COMMENT 'Total de transações recebidas nas últimas 24h',
            unique_senders        BIGINT    COMMENT 'EOAs distintos que interagiram',
            total_eth_received    DOUBLE    COMMENT 'Volume total de ETH recebido (Wei ÷ 1e18)',
            avg_eth_per_tx        DOUBLE    COMMENT 'Média de ETH por transação',
            first_seen            TIMESTAMP COMMENT 'Primeira transação na janela de 24h',
            last_seen             TIMESTAMP COMMENT 'Última transação na janela de 24h',
            computed_at           TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV (UC7): ranking de contratos por volume de ETH recebido nas últimas 24h.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_apps.contract_volume_ranking", cat)

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
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.network_metrics_hourly", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_network.eth_burn_hourly (
            hour_bucket                TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            block_count                BIGINT    COMMENT 'Blocos produzidos na hora',
            eth_burned_total           DOUBLE    COMMENT 'ETH total queimado na hora (base_fee × gas_used / 1e18)',
            eth_burned_per_block_avg   DOUBLE    COMMENT 'ETH queimado médio por bloco',
            eth_burned_per_block_max   DOUBLE    COMMENT 'ETH queimado máximo por bloco',
            avg_base_fee_gwei          DOUBLE    COMMENT 'Taxa base média em Gwei',
            max_base_fee_gwei          DOUBLE    COMMENT 'Taxa base máxima em Gwei',
            avg_block_utilization_pct  DOUBLE    COMMENT 'Utilização média de gas dos blocos',
            computed_at                TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV: ETH queimado por hora via EIP-1559 (base_fee × gas_used). Indicador de atividade de rede e deflação.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.eth_burn_hourly", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_network.validator_activity (
            fee_recipient      STRING    COMMENT 'Endereço do validador (fee recipient em PoS)',
            blocks_produced    BIGINT    COMMENT 'Blocos produzidos pelo validador nas últimas 24h',
            total_blocks_24h   BIGINT    COMMENT 'Total de blocos na rede nas últimas 24h',
            pct_share          DOUBLE    COMMENT 'Participação percentual do validador',
            hhi_component      DOUBLE    COMMENT 'Componente HHI deste validador (pct_share²)',
            hhi_total          DOUBLE    COMMENT 'HHI total da rede (<1500=descentralizado, 1500-2500=moderado, >2500=concentrado)',
            first_block_time   TIMESTAMP COMMENT 'Timestamp do primeiro bloco na janela',
            last_block_time    TIMESTAMP COMMENT 'Timestamp do último bloco na janela',
            computed_at        TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV: concentração de validadores Ethereum nas últimas 24h — HHI e participação percentual.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.validator_activity", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_network.withdrawal_metrics (
            hour_bucket                TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            withdrawal_count           BIGINT    COMMENT 'Total de saques na hora',
            unique_validators          BIGINT    COMMENT 'Validadores únicos que sacaram',
            unique_addresses           BIGINT    COMMENT 'Endereços de destino únicos',
            total_eth_withdrawn        DOUBLE    COMMENT 'Volume total de ETH sacado na hora',
            avg_eth_per_withdrawal     DOUBLE    COMMENT 'Média de ETH por saque',
            max_single_withdrawal_eth  DOUBLE    COMMENT 'Maior saque individual em ETH',
            min_single_withdrawal_eth  DOUBLE    COMMENT 'Menor saque individual em ETH',
            computed_at                TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV: fluxo horário de saques da Beacon Chain (EIP-4895). Indicador de pressão de venda e concentração de stake.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.withdrawal_metrics", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_network.block_production_health (
            hour_bucket             TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            block_count             BIGINT    COMMENT 'Blocos produzidos na hora',
            missed_slots_estimated  BIGINT    COMMENT 'Slots perdidos estimados (gap > 12s)',
            missed_slot_rate_pct    DOUBLE    COMMENT 'Taxa de slots perdidos (missed / (blocks + missed) × 100)',
            avg_slot_gap_sec        DOUBLE    COMMENT 'Gap médio entre blocos em segundos',
            max_slot_gap_sec        DOUBLE    COMMENT 'Maior gap entre blocos em segundos',
            gap_events_count        BIGINT    COMMENT 'Número de eventos com gap > 12s',
            computed_at             TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV: saúde horária da produção de blocos — slots perdidos e gaps de intervalo.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.block_production_health", cat)

        self._sql(f"""
          CREATE TABLE IF NOT EXISTS `{cat}`.g_network.chain_health_metrics (
            hour_bucket         TIMESTAMP COMMENT 'Hora de início da janela de agregação',
            total_blocks        BIGINT    COMMENT 'Total de blocos no período',
            canonical_count     BIGINT    COMMENT 'Blocos canônicos',
            orphan_count        BIGINT    COMMENT 'Blocos orphan (forks resolvidos)',
            unconfirmed_count   BIGINT    COMMENT 'Blocos não confirmados (recentes)',
            orphan_rate_pct     DOUBLE    COMMENT 'Taxa de orphan blocks (orphan / total × 100)',
            computed_at         TIMESTAMP COMMENT 'Timestamp de computação desta MV'
          )
          COMMENT 'Gold MV: saúde horária da cadeia — taxa de orphan blocks. Orphan rate alto indica instabilidade de rede.'
          TBLPROPERTIES ('quality' = 'gold', 'pipelines.autoOptimize.managed' = 'true')
        """)
        _log.info("Table ensured: %s.g_network.chain_health_metrics", cat)

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
