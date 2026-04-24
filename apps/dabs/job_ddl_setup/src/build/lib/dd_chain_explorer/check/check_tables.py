"""check_tables.py — Verifica row counts de tabelas Bronze/Silver/Gold."""
import argparse
import logging
import sys

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Tabelas que devem ter pelo menos 1 linha após um ciclo completo de pipelines.
# Formato: (schema, table) — o catálogo é injetado via --catalog.
EXPECTED_TABLES = [
    # Bronze — DLT pipeline_ethereum
    ("b_ethereum", "eth_mined_blocks"),
    ("b_ethereum", "eth_transactions"),
    ("b_ethereum", "eth_txs_input_decoded"),
    # Bronze — DLT pipeline_app_logs
    ("b_app_logs", "b_app_logs_data"),
    # Silver — DLT pipeline_ethereum
    ("s_apps", "eth_blocks"),
    ("s_apps", "eth_transactions_staging"),
    ("s_apps", "transactions_ethereum"),
    ("s_apps", "eth_blocks_withdrawals"),
    ("s_apps", "eth_canonical_blocks_index"),
    ("s_apps", "txs_inputs_decoded_fast"),
    # Silver — DLT pipeline_app_logs
    ("s_logs", "logs_streaming"),
    ("s_logs", "logs_batch"),
    # Gold — g_apps (DLT pipeline_ethereum)
    ("g_apps", "popular_contracts_ranking"),
    ("g_apps", "peer_to_peer_txs"),
    ("g_apps", "ethereum_gas_consume"),
    ("g_apps", "transactions_lambda"),
    ("g_apps", "gas_price_distribution_hourly"),
    ("g_apps", "p2p_transfer_metrics_hourly"),
    ("g_apps", "contract_method_activity"),
    ("g_apps", "contract_deploy_metrics_hourly"),
    ("g_apps", "contract_volume_ranking"),
    # Gold — g_network (DLT pipeline_ethereum)
    ("g_network", "network_metrics_hourly"),
    ("g_network", "eth_burn_hourly"),
    ("g_network", "validator_activity"),
    ("g_network", "chain_health_metrics"),
    ("g_network", "withdrawal_metrics"),
    ("g_network", "block_production_health"),
    # Gold — g_api_keys (DLT pipeline_app_logs)
    ("g_api_keys", "etherscan_consumption"),
    ("g_api_keys", "web3_keys_consumption"),
]

# Tabelas que podem ter 0 linhas sem ser erro crítico:
#   - MVs com filtro de janela temporal (1h/24h) — podem esvaziar fora do janela
#   - MVs data-dependentes (ex.: deploys de contrato) — dependem de eventos raros
#   - logs_batch — o crawler batch pode não ter rodado no ambiente DEV
# 0 linhas nessas tabelas gera WARN, não FAIL.
SOFT_CHECK_TABLES: frozenset[tuple[str, str]] = frozenset([
    ("g_apps", "popular_contracts_ranking"),      # 1h sliding window
    ("g_apps", "contract_method_activity"),        # 24h sliding window
    ("g_apps", "contract_volume_ranking"),         # 24h sliding window
    ("g_network", "validator_activity"),           # 24h sliding window
    ("g_apps", "contract_deploy_metrics_hourly"),  # data-dependent (contract creation txs)
    ("s_logs", "logs_batch"),                      # batch crawler may not run in DEV/HML
])


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Bronze/Silver/Gold row counts")
    parser.add_argument("--catalog", required=True, help="Unity Catalog name (e.g. dev)")
    parser.add_argument(
        "--no-fail-on-empty",
        action="store_true",
        default=False,
        help="Print results but exit 0 even when tables are empty",
    )
    args = parser.parse_args()

    try:
        from pyspark.sql import SparkSession  # noqa: PLC0415

        spark = SparkSession.builder.getOrCreate()
        if spark is None:
            raise RuntimeError("Failed to acquire SparkSession.")
    except ImportError as exc:
        _log.error("PySpark not available: %s", exc)
        sys.exit(1)

    cat = args.catalog
    failures: list[str] = []

    _log.info("Checking %d tables in catalog '%s'...", len(EXPECTED_TABLES), cat)
    _log.info("%-60s %s", "Table", "Status")
    _log.info("-" * 80)

    for schema, table in EXPECTED_TABLES:
        full = f"`{cat}`.{schema}.{table}"
        is_soft = (schema, table) in SOFT_CHECK_TABLES
        try:
            count = spark.sql(f"SELECT count(*) AS n FROM {full}").collect()[0]["n"]
            if count > 0:
                _log.info("%-60s PASS  (%d rows)", full, count)
            elif is_soft:
                _log.warning("%-60s WARN  (0 rows — soft check, acceptable)", full)
            else:
                _log.warning("%-60s FAIL  (0 rows)", full)
                failures.append(full)
        except Exception as exc:  # noqa: BLE001
            _log.warning("%-60s ERROR (%s)", full, exc)
            failures.append(full)

    _log.info("-" * 80)

    if failures:
        _log.warning("Tables with issues (%d): %s", len(failures), failures)
        if not args.no_fail_on_empty:
            sys.exit(1)
    else:
        _log.info("All %d tables OK.", len(EXPECTED_TABLES))


if __name__ == "__main__":
    main()
