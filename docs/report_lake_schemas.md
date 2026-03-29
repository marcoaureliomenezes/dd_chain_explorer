# Lake Schemas Report

> Gerado em: 2026-03-29 21:22 UTC | Ambiente: dev | Catálogo: `dev` | Hash: `94d126df05044559`

## Resumo

| Status | Entidades |
|--------|-----------|
| ✅ OK | 0 |
| ❌ STALE (no catálogo, não no código) | 0 |
| ⚠️ MISSING (no código, não no catálogo) | 21 |

## ⚠️ Entidades MISSING

Definidas no código mas ausentes no catálogo:

| Schema | Nome | Tipo | Fonte |
|--------|------|------|-------|
| `(pipeline default)` | `b_app_logs_data` | TABLE | DLT:5_pipeline_app_logs.py |
| `(pipeline default)` | `b_blocks_data` | TABLE | DLT:4_pipeline_ethereum.py |
| `(pipeline default)` | `b_transactions_data` | TABLE | DLT:4_pipeline_ethereum.py |
| `(pipeline default)` | `b_transactions_decoded` | TABLE | DLT:4_pipeline_ethereum.py |
| `(pipeline default)` | `logs_batch` | TABLE | DLT:5_pipeline_app_logs.py |
| `(pipeline default)` | `logs_streaming` | TABLE | DLT:5_pipeline_app_logs.py |
| `b_ethereum` | `popular_contracts_txs` | TABLE | DDL:setup_ddl.py |
| `g_api_keys` | `api_keys_visibility_filter` | FUNCTION | DDL:setup_ddl.py |
| `g_api_keys` | `etherscan_consumption` | TABLE | DLT:5_pipeline_app_logs.py |
| `g_api_keys` | `web3_keys_consumption` | TABLE | DLT:5_pipeline_app_logs.py |
| `g_network` | `network_metrics_hourly` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `blocks_fast` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `blocks_withdrawals` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `ethereum_gas_consume` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `peer_to_peer_txs` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `popular_contracts_ranking` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `transactions_batch` | TABLE | DDL:setup_ddl.py |
| `s_apps` | `transactions_ethereum` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `transactions_fast` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `transactions_lambda` | TABLE | DLT:4_pipeline_ethereum.py |
| `s_apps` | `txs_inputs_decoded_fast` | TABLE | DLT:4_pipeline_ethereum.py |
