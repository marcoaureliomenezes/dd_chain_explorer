# Lake ROADMAP — DD Chain Explorer

Roadmap de organização e otimização do Data Lake no Unity Catalog.

---

## Estado após limpeza inicial (2026-04-04)

### Catálogos removidos
| Catálogo | Motivo |
|----------|--------|
| `prd` | Vazio — nenhum schema ou tabela |
| `learn` | Sample tables Databricks (`nyc.*`) — sem relação com o projeto |

### Tabelas stale deletadas
| Tabela | Tipo | Motivo |
|--------|------|--------|
| `dev.b_ethereum.popular_contracts_txs` | EXTERNAL Bronze | Pipeline batch (Etherscan API) deprecated — job `dm-batch-contracts` removido |
| `dev.s_apps.transactions_batch` | EXTERNAL Silver | Downstream da tabela acima — empty, nunca populada |
| `dev.b_app_logs.logs_streaming` | STREAMING_TABLE | Movida para `dev.s_logs.logs_streaming` (schema correto) |
| `dev.b_app_logs.logs_batch` | STREAMING_TABLE | Movida para `dev.s_logs.logs_batch` (schema correto) |
| `dev.s_apps.ethereum_gas_consume` | MATERIALIZED_VIEW | Migrada para `dev.g_apps.ethereum_gas_consume` (tier correto) |
| `dev.s_apps.peer_to_peer_txs` | MATERIALIZED_VIEW | Migrada para `dev.g_apps.peer_to_peer_txs` (tier correto) |
| `dev.s_apps.popular_contracts_ranking` | MATERIALIZED_VIEW | Migrada para `dev.g_apps.popular_contracts_ranking` (tier correto) |
| `dev.s_apps.transactions_lambda` | MATERIALIZED_VIEW | Migrada para `dev.g_apps.transactions_lambda` + refatorada (sem batch) |

### Bugs de código corrigidos
- `5_pipeline_app_logs.py` — Silver tables `logs_streaming` e `logs_batch` agora escrevem em `s_logs.*` em vez de `b_app_logs.*`
- `4_pipeline_ethereum.py` — Gold MVs renomeadas de `s_apps.*` para `g_apps.*`
- `4_pipeline_ethereum.py` — `transactions_lambda` refatorada: removida dependência de `b_ethereum.popular_contracts_txs` (stale); agora é streaming-only
- `setup_ddl.py` — schemas atualizados (adicionado `g_apps`); EXTERNAL tables stale removidas
- `databricks.yml` — `workflow_batch_contracts` removido do include (job deprecated)

---

## Arquitetura atual do catálogo DEV (estado limpo)

```
dev/
├── b_app_logs/                   ← Bronze: logs raw
│   └── b_app_logs_data           STREAMING_TABLE (pipeline dm-app-logs)
│
├── b_ethereum/                   ← Bronze: dados Ethereum raw
│   ├── b_blocks_data             STREAMING_TABLE (pipeline dm-ethereum)
│   ├── b_transactions_data       STREAMING_TABLE
│   └── b_transactions_decoded    STREAMING_TABLE
│
├── s_apps/                       ← Silver: dados Ethereum enriquecidos
│   ├── blocks_fast               STREAMING_TABLE
│   ├── blocks_withdrawals        STREAMING_TABLE
│   ├── transactions_fast         STREAMING_TABLE
│   ├── txs_inputs_decoded_fast   STREAMING_TABLE
│   └── transactions_ethereum     STREAMING_TABLE (JOIN enriched)
│
├── s_logs/                       ← Silver: logs processados
│   ├── logs_streaming            STREAMING_TABLE (pipeline dm-app-logs)
│   └── logs_batch                STREAMING_TABLE
│
├── g_apps/                       ← Gold: visões analíticas Ethereum
│   ├── popular_contracts_ranking MATERIALIZED_VIEW (top 100 contratos/hora)
│   ├── peer_to_peer_txs          MATERIALIZED_VIEW (transações EOA→EOA)
│   ├── ethereum_gas_consume      MATERIALIZED_VIEW (consumo de gas classificado)
│   └── transactions_lambda       MATERIALIZED_VIEW (contratos populares + decode)
│
├── g_api_keys/                   ← Gold: monitoramento de API keys
│   ├── etherscan_consumption     MATERIALIZED_VIEW
│   └── web3_keys_consumption     MATERIALIZED_VIEW
│
└── g_network/                    ← Gold: métricas de rede
    └── network_metrics_hourly    MATERIALIZED_VIEW
```

---

## TODOs pendentes

### Alta prioridade

- [ ] **TODO-L01** — Validar `g_apps.*` após re-run completo do pipeline `dm-ethereum`
  - Confirmar que as 4 Gold MVs foram recriadas em `g_apps` com dados
  - Query: `SELECT COUNT(*) FROM dev.g_apps.popular_contracts_ranking`

- [ ] **TODO-L02** — Validar `s_logs.*` após re-run do pipeline `dm-app-logs`
  - Confirmar que `s_logs.logs_streaming` e `s_logs.logs_batch` estão populadas
  - Query: `SELECT COUNT(*) FROM dev.s_logs.logs_streaming`

- [ ] **TODO-L03** — Atualizar dashboards para referenciar `g_apps.*` em vez de `s_apps.*`
  - Verificar: `resources/dashboards/*.yml` — queries com `s_apps.ethereum_gas_consume`, `s_apps.peer_to_peer_txs`, `s_apps.popular_contracts_ranking`, `s_apps.transactions_lambda`

- [ ] **TODO-L04** — Atualizar `4_export_gold_to_s3.py` para incluir exports de `g_apps.*`
  - Atualmente só exporta `g_api_keys.*` para S3
  - Considerar adicionar export de `g_apps.popular_contracts_ranking` e `g_apps.transactions_lambda`

### Média prioridade

- [ ] **TODO-L05** — Revisão do schema `g_network`
  - `network_metrics_hourly` existe mas está marcada como `TODO-P06` no pipeline
  - Verificar se a implementação está completa ou apenas um stub

- [ ] **TODO-L06** — Revisar `transactions_lambda` simplificada
  - A MV agora une `transactions_ethereum` (streaming) com `popular_contracts_ranking`
  - Avaliar se é necessário manter deduplicação por `tx_hash` (antes feita com batch)
  - Possível: adicionar `DISTINCT` ou window por `tx_hash` se houver duplicatas

- [ ] **TODO-L07** — Adicionar schema `g_apps` ao `setup_ddl.py --drop` para HML/PROD
  - `DDChainExplorerDDL.ALL_SCHEMAS` já foi atualizado com `g_apps`
  - Verificar se o workflow `dm-ddl-setup` roda corretamente no próximo deploy HML

- [ ] **TODO-L08** — Validar pipeline `dm-app-logs` para `s_logs` funcionar em HML/PROD
  - O `pipeline_app_logs.yml` usa `target: b_app_logs` — tabelas sem prefixo de schema aterram ali
  - Após a correção (`name="s_logs.logs_streaming"`), verificar se o DLT respeita o schema explícito
  - Pode ser necessário ajustar o `target` no YAML

### Baixa prioridade / Backlog

- [ ] **TODO-L09** — Deprecar `workflow_batch_contracts.yml` do repositório
  - O arquivo `resources/workflows/workflow_batch_contracts.yml` ainda existe no repo
  - Foi removido do `databricks.yml` include, mas o arquivo pode ser deletado do repositório
  - Remover também `src/dd_chain_explorer/batch_contracts/` se não usado por outro workflow

- [ ] **TODO-L10** — Avaliar arquitetura Lambda para contratos populares
  - A arquitetura Lambda (streaming + batch) foi simplificada para streaming-only
  - Se a cobertura histórica for necessária, avaliar ingestão via Spark batch (não API Etherscan)
  - Alternativa: usar `transactions_ethereum` com janela de tempo maior (dias em vez de 1h)

- [ ] **TODO-L11** — Alertas e monitoramento do catálogo DEV
  - `resources/alerts/alert_api_keys_threshold.yml` e `alert_dynamodb_deadlock.yml` estão no bundle mas com warnings de campos `unknown`
  - Verificar se esses recursos são suportados na versão atual do CLI ou se precisam de atualização

---

## Convenção de nomenclatura (referência)

| Prefixo | Tier | Conteúdo |
|---------|------|----------|
| `b_*` | Bronze | Dados raw ingeridos diretamente das fontes |
| `s_*` | Silver | Dados limpos, tipados e enriquecidos |
| `g_*` | Gold | Materialized Views analíticas — prontas para consumo |

| Schema | Domínio |
|--------|---------|
| `b_ethereum` | Blocos e transações Ethereum (streaming) |
| `b_app_logs` | Logs das aplicações on-chain (CloudWatch → S3 → DLT) |
| `s_apps` | Silver Ethereum: tabelas enriquecidas |
| `s_logs` | Silver Logs: logs processados por tipo de aplicação |
| `g_apps` | Gold Ethereum: visões analíticas de transações |
| `g_api_keys` | Gold: consumo de API keys (Etherscan, Alchemy, Infura) |
| `g_network` | Gold: métricas horárias da rede Ethereum |
