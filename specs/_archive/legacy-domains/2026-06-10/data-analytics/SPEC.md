# Spec: Domínio — Data Analytics

> **Status:** Implementado (dashboards Lakeview quebrados — precisam de reconstrução)
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/data-catalog.md`, `specs/memory/architecture.md`

---

## Escopo

Toda a camada de serving analítico do DD Chain Explorer:
- **4 Dashboards Lakeview** (`apps/dabs/dashboard_*/`)
- **1 Genie Space** (`apps/dabs/genie_ethereum/`)
- **2 Alerts Databricks** (`apps/dabs/alert_*/`)

Este domínio NÃO inclui: pipelines DLT, batch jobs de processamento, infraestrutura Terraform, CI/CD.

---

## Componentes

### Dashboards Lakeview

| Componente | Status | Métricas-chave |
|------------|--------|----------------|
| `dashboard_network_overview` | Quebrado | TPS, blocos/min, txs por bloco, atividade da rede |
| `dashboard_gas_analytics` | Quebrado | Gas price distribution, burn rate EIP-1559, gas por tipo de tx |
| `dashboard_hot_contracts` | Quebrado | Top contratos por volume de txs, unique senders, last_seen |
| `dashboard_api_health` | Quebrado | Consumo Etherscan/Infura por key, rotação, thresholds |

**Contexto:** Os dashboards existem como DABs mas estão quebrados. Os dados Gold estão disponíveis e corretos — o problema é de configuração de queries e widgets, não de dados.

### Genie Space

| Componente | Status | Tabelas expostas |
|------------|--------|-----------------|
| `genie_ethereum` | Desconhecido | MVs Gold: popular_contracts_ranking, peer_to_peer_txs, network_metrics_hourly |

### Alerts

| Componente | Condição de disparo | Severidade |
|------------|---------------------|-----------|
| `alert_api_keys` | Consumo Etherscan ou Web3 keys > threshold | P2 |
| `alert_dynamodb_deadlock` | Count de deadlocks no semáforo DynamoDB > 0 | P1 |

---

## Dados Gold Disponíveis

Todas as fontes para dashboards e Genie estão nos schemas Gold:

| Schema | MVs principais | Dados |
|--------|---------------|-------|
| `g_apps` | `popular_contracts_ranking` | Top contratos: tx_count, unique_senders, first/last_seen |
| `g_apps` | `peer_to_peer_txs` | EOA→EOA: tx_hash, from, to, value, gas, timestamp |
| `g_apps` | `gas_price_distribution_hourly` | Gas price por hora: min, max, median, avg |
| `g_apps` | `ethereum_gas_consume` | Gas por tipo: contract_deploy, p2p, contract_interaction |
| `g_apps` | `transactions_lambda` | Txs completas (union streaming + batch) com decode |
| `g_network` | `network_metrics_hourly` | TPS, blocos/h, txs/bloco, gas total |
| `g_api_keys` | `etherscan_consumption` | Chamadas Etherscan por key, por hora |
| `g_api_keys` | `web3_keys_consumption` | Chamadas Infura/Alchemy por key, por hora |

---

## Requisitos Funcionais

### Dashboards

**FR-DA-001 — Dados via SQL Warehouse**
Todos os dashboards devem usar `${var.warehouse_id}` — nunca hardcode de warehouse ou cluster.

**FR-DA-002 — Reconstrução dos dashboards**
Os 4 dashboards existentes devem ser reconstruídos apontando para as MVs Gold corretas. Fundamentos (componentes DABs) existem — o trabalho é reconfigurar queries e widgets.

**FR-DA-003 — Catalog via variável**
Todas as queries nos dashboards devem usar `${var.catalog}` — nunca hardcode de catalog name.

**FR-DA-004 — Scaffold obrigatório**
Novos dashboards devem ser criados via `beteugeuse dashboard create` (quando disponível). Enquanto não disponível, copiar estrutura do componente mais próximo.

### Genie Space

**FR-DA-010 — Tabelas expostas ao Genie**
O `genie_ethereum` deve expor apenas tabelas Gold (`g_apps`, `g_network`, `g_api_keys`) — nunca Bronze ou Silver diretamente.

**FR-DA-011 — Instruções de contexto**
O Genie Space deve incluir instruções de contexto explicando o domínio (Ethereum analytics) para que o modelo gere queries relevantes.

### Alerts

**FR-DA-020 — Alert api_keys**
O alert deve disparar quando o consumo de qualquer API key (Etherscan ou Infura/Alchemy) exceder 80% do limite horário configurável.

**FR-DA-021 — Alert deadlock**
O alert deve disparar quando `COUNT(SEMAPHORE entities com TTL expirado mas não limpos)` > 0, indicando que um job travou sem liberar a key.

---

## Padrões de Implementação

- Todo componente é um DABs autônomo com `databricks.yml` e 3 targets (dev/hml/prod)
- Deploy via `databricks bundle deploy --target dev` para validação
- Nunca criar ou modificar dashboards/Genie via SDK diretamente — apenas via DABs
- Desenvolvimento em DEV ou HML — nunca acessar dados de PRD durante desenvolvimento

---

## Requisitos Não-Funcionais

- **NFR-DA-001:** Dashboards devem carregar em < 3 segundos usando SQL Warehouse serverless.
- **NFR-DA-002:** Genie Space deve ser capaz de responder perguntas sobre contratos populares, gas e atividade de rede sem precisar de joins manuais pelo usuário.
- **NFR-DA-003:** Alerts devem disparar em < 5 minutos após a condição ser detectada.

---

## Fora de Escopo (v1)

- Dashboards públicos (sem autenticação Databricks)
- Integração de dados externos além das tabelas Gold internas
- Alertas por email/Slack (hoje: apenas notificação nativa Databricks)
