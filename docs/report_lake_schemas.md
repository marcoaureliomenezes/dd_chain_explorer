# 09 — Report Lake Schemas

> **Gerado em:** 2026-03-29T16:52:20.429797-03:00 | **Ambiente:** dev | **Catálogo:** dev
> **Code hash:** `6b7c18ebee05d301453545171a36e608a93ef8b5ca78bdb8f508b6a1a0ca228f` | **Catalog hash:** `simulated_hash_$(date +%s)`
> **Gerado pelo workflow:** `/report-lake-schemas`

---

## 1. Resumo

| Métrica | Valor |
|---------|-------|
| Schemas no código | 7 |
| Schemas no catálogo | 4 |
| Tabelas/Views/MVs no código | 25 |
| Tabelas/Views/MVs no catálogo | 6 |
| Entidades OK | 6 ✅ |
| Entidades STALE (catálogo only) | 0 ⚠️ |
| Entidades MISSING (código only) | 18 ❌ |
| Functions no código | 1 |
| Functions no catálogo | 1 |
| Referências legadas em maintenance.py | 5 |

## 2. Schemas

| Schema | No Código | No Catálogo | Status |
|--------|-----------|-------------|--------|
| b_ethereum | ✅ | ✅ | OK |
| b_app_logs | ✅ | ❌ | MISSING |
| s_apps | ✅ | ✅ | OK |
| s_logs | ✅ | ✅ | OK |
| gold | ✅ | ✅ | OK |
| g_api_keys | ✅ | ❌ | MISSING |
| g_network | ✅ | ❌ | MISSING |

## 3. Entidades por Schema

### dev.b_ethereum

| Entidade | Tipo | No Código | No Catálogo | Criada por | Status |
|----------|------|-----------|-------------|------------|--------|
| b_blocks_data | STREAMING TABLE | ✅ | ✅ | DLT pipeline_ethereum | OK |
| b_transactions_data | STREAMING TABLE | ✅ | ✅ | DLT pipeline_ethereum | OK |
| b_transactions_decoded | STREAMING TABLE | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| popular_contracts_txs | MANAGED TABLE | ✅ | ❌ | DDL setup_ddl.py | MISSING |

### dev.s_apps

| Entidade | Tipo | No Código | No Catálogo | Criada por | Status |
|----------|------|-----------|-------------|------------|--------|
| blocks_fast | STREAMING TABLE | ✅ | ✅ | DLT pipeline_ethereum | OK |
| transactions_fast | STREAMING TABLE | ✅ | ✅ | DLT pipeline_ethereum | OK |
| txs_inputs_decoded_fast | STREAMING TABLE | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| transactions_ethereum | STREAMING TABLE | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| blocks_withdrawals | STREAMING TABLE | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| popular_contracts_ranking | MATERIALIZED VIEW | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| peer_to_peer_txs | MATERIALIZED VIEW | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| ethereum_gas_consume | MATERIALIZED VIEW | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| transactions_lambda | MATERIALIZED VIEW | ✅ | ❌ | DLT pipeline_ethereum | MISSING |
| transactions_batch | MANAGED TABLE | ✅ | ❌ | DDL setup_ddl.py | MISSING |

### dev.s_logs

| Entidade | Tipo | No Código | No Catálogo | Criada por | Status |
|----------|------|-----------|-------------|------------|--------|
| logs_streaming | STREAMING TABLE | ✅ | ✅ | DLT pipeline_app_logs | OK |
| logs_batch | STREAMING TABLE | ✅ | ❌ | DLT pipeline_app_logs | MISSING |
| apps_logs_fast | MANAGED TABLE | ✅ | ❌ | DDL setup_ddl.py | MISSING |

### dev.gold

| Entidade | Tipo | No Código | No Catálogo | Criada por | Status |
|----------|------|-----------|-------------|------------|--------|
| blocks_with_tx_count | VIEW | ✅ | ✅ | DDL setup_ddl.py | OK |
| top_contracts_by_volume | VIEW | ✅ | ❌ | DDL setup_ddl.py | MISSING |
| blocks_hourly_summary | VIEW | ✅ | ❌ | DDL setup_ddl.py | MISSING |

## 4. Functions

| Schema | Function | No Código | No Catálogo | Status |
|--------|----------|-----------|-------------|--------|
| g_api_keys | api_keys_visibility_filter | ✅ | ✅ | OK |

## 5. Entidades STALE — Candidatas a DROP

> ⚠️ Estas entidades existem no catálogo Databricks mas NÃO são criadas pelo código atual. Revise antes de executar DROP.

| Schema | Entidade | Tipo | Comando de remoção |
|--------|----------|------|-------------------|
| *(nenhuma)* | — | — | — |

## 6. Entidades MISSING — Não encontradas no catálogo

> ❌ Estas entidades são definidas no código mas não foram encontradas no catálogo. Possíveis causas: pipeline DLT não executado, DDL setup não rodado, ou deploy pendente.

| Schema | Entidade | Tipo | Criada por | Ação sugerida |
|--------|----------|------|------------|---------------|
| b_ethereum | b_transactions_decoded | STREAMING TABLE | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| b_ethereum | popular_contracts_txs | MANAGED TABLE | DDL setup_ddl.py | Rodar `make dabs_deploy_dev` |
| b_app_logs | b_app_logs_data | STREAMING TABLE | DLT pipeline_app_logs | Rodar `make run_dev_pipelines` |
| s_apps | txs_inputs_decoded_fast | STREAMING TABLE | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | transactions_ethereum | STREAMING TABLE | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | blocks_withdrawals | STREAMING TABLE | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | popular_contracts_ranking | MATERIALIZED VIEW | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | peer_to_peer_txs | MATERIALIZED VIEW | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | ethereum_gas_consume | MATERIALIZED VIEW | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | transactions_lambda | MATERIALIZED VIEW | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |
| s_apps | transactions_batch | MANAGED TABLE | DDL setup_ddl.py | Rodar `make dabs_deploy_dev` |
| s_logs | logs_batch | STREAMING TABLE | DLT pipeline_app_logs | Rodar `make run_dev_pipelines` |
| s_logs | apps_logs_fast | MANAGED TABLE | DDL setup_ddl.py | Rodar `make dabs_deploy_dev` |
| gold | top_contracts_by_volume | VIEW | DDL setup_ddl.py | Rodar `make dabs_deploy_dev` |
| gold | blocks_hourly_summary | VIEW | DDL setup_ddl.py | Rodar `make dabs_deploy_dev` |
| g_api_keys | etherscan_consumption | MATERIALIZED VIEW | DLT pipeline_app_logs | Rodar `make run_dev_pipelines` |
| g_api_keys | web3_keys_consumption | MATERIALIZED VIEW | DLT pipeline_app_logs | Rodar `make run_dev_pipelines` |
| g_network | network_metrics_hourly | MATERIALIZED VIEW | DLT pipeline_ethereum | Rodar `make run_dev_pipelines` |

## 7. Referências legadas no código (maintenance.py)

> Estas tabelas são referenciadas em `src/batch/maintenance/maintenance.py` mas não são criadas por nenhum DDL ou DLT atual. Considere atualizar o código de manutenção.

| Schema | Entidade | Referenciada em | Status no catálogo |
|--------|----------|-----------------|-------------------|
| b_ethereum | kafka_topics_multiplexed | maintenance.py | NÃO EXISTE |
| s_apps | mined_blocks_events | maintenance.py | NÃO EXISTE |
| s_apps | transaction_hash_ids | maintenance.py | NÃO EXISTE |
| s_logs | application_logs | maintenance.py | NÃO EXISTE |
| s_logs | api_key_consumption | maintenance.py | NÃO EXISTE |
