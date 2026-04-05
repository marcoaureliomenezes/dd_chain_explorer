# Análise de Dados — Transações Ethereum

> Relatório técnico: classificação semântica dos campos Bronze, diagnóstico do modelo Silver
> atual, proposta de Silver fonte da verdade, classificação de tipos de transação, casos de
> uso Gold e TODOs sequenciados com checkpoints de validação.
> Pipeline: `dlt_ethereum` · Catálogo Unity Catalog (`dev`/`dd_chain_explorer`)

---

## Sumário

1. [Classificação Semântica dos Campos Bronze — `eth_transactions`](#1-classificação-semântica-dos-campos-bronze--eth_transactions)
2. [Tabela Decoded — `eth_txs_input_decoded`](#2-tabela-decoded--eth_txs_input_decoded)
3. [Diagrama do Pipeline Bronze → Silver → Gold](#3-diagrama-do-pipeline-bronze--silver--gold)
4. [Diagnóstico do Modelo Atual](#4-diagnóstico-do-modelo-atual)
5. [Proposta de Modelo Futuro](#5-proposta-de-modelo-futuro)
6. [Casos de Uso Gold](#6-casos-de-uso-gold)
7. [TODOs Detalhados e Sequenciados](#7-todos-detalhados-e-sequenciados)
8. [Validação do Estado Real — Queries Databricks](#8-validação-do-estado-real--queries-databricks)
9. [Referências de Arquivos](#9-referências-de-arquivos)

---

## 1. Classificação Semântica dos Campos Bronze — `eth_transactions`

A tabela Bronze `b_ethereum.eth_transactions` (também registrada como `b_ethereum.b_transactions_data`
na DDL legada — ver [Seção 4.1](#41-divergência-de-nomenclatura)) contém **16 campos** originados do
stream Firehose `mainnet-transactions-data` → S3 NDJSON → Auto Loader, mais 2 adicionados pelo pipeline.

### 1.1 Identidade & Posição na Cadeia

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `hash` | string | `tx_hash` | ✅ propagar | Hash keccak256 da transação assinada. Único e imutável. Chave natural para deduplicação UNION streaming + batch. |
| `blockNumber` | long | `block_number` | ✅ propagar | Altura do bloco. Indexação e JOIN com tabelas de blocos. |
| `blockHash` | string | `block_hash` | ✅ propagar | Hash do bloco. Necessário para identificar fork via `eth_canonical_blocks_index`. |
| `transactionIndex` | long | `transaction_index` | ✅ propagar | Posição 0-based no bloco. Determina ordem de execução; relevante para análise de MEV. |

### 1.2 Endereços — Remetente e Destinatário

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `from` | string | `from_address` | ✅ propagar | EOA que assinou a transação. Sempre não-nulo. Validado via `RLIKE '^0x[a-fA-F0-9]{40}$'`. |
| `to` | string | `to_address` | ✅ propagar | Endereço de destino. **Nulo = deploy de contrato**. Validado via `IS NULL OR RLIKE`. |

> **`to IS NULL` = deploy de contrato**: quando nulo, o campo `input` contém o bytecode EVM (initcode). O endereço do contrato criado é derivado deterministicamente: `keccak256(RLP(from, nonce))[12:]`. Esta é a regra canônica para classificar deploys diretamente na Bronze.

### 1.3 Valor Transferido

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `value` | string | `value` | ✅ propagar (STRING) | Valor em Wei (1 ETH = 10¹⁸ Wei). **Não converter para DOUBLE na Silver** — perda de precisão em valores grandes. Conversão `value_eth = DOUBLE` deve ser campo derivado somente no Gold. |

### 1.4 Calldata — Alto Valor Analítico para Classificação ★

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `input` | string | `input` | ✅ propagar | Payload hexadecimal enviado ao contrato. Estrutura: `0x` + **4 bytes** (seletor de função = keccak256(assinatura)[0:4]) + **N bytes** (parâmetros ABI-encoded). Quando `input IN ('', '0x', NULL)`: transferência ETH simples. Quando `to IS NULL` e input não vazio: bytecode de deploy. |

**Estrutura do campo `input` por tipo de transação:**

```
input = '0x' | NULL | ''
    → Transferência ETH pura (sem calldata)

input = '0x' + [4 bytes seletor] + [ABI encoded params]
    → Chamada de função de contrato
    Exemplo: '0xa9059cbb' = selector de transfer(address,uint256)

input = bytecode EVM (quando to IS NULL)
    → Deploy de contrato — EVM initcode
```

> **O seletor de 4 bytes como chave analítica**: `SUBSTRING(input, 3, 8)` retorna o `method_id`. É possível identificar funções conhecidas via [4byte.directory](https://www.4byte.directory/signatures/) sem ABI completa — estratégia já usada pelo decoder.

### 1.5 Gas & Economia — Valor Analítico Parcial ★

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `gas` | string | `gas` | ✅ propagar (STRING) | **Gas limit** definido pelo remetente. **Não confundir com gas efetivamente consumido** (`gas_used` do receipt — indisponível no streaming Firehose). |
| `gasPrice` | string | `gas_price` | ✅ propagar (STRING) | Preço por unidade de gas em Wei. Em type-2 (EIP-1559): effective price propagado na rede. Os campos `maxFeePerGas` / `maxPriorityFeePerGas` não chegam no stream atual. |

> **Limitação crítica do streaming**: `gas` é o **limite** definido pelo remetente, não o consumido real (`gas_used` do receipt). Uma tx com `gas = 200000` pode ter consumido apenas `gas_used = 21000`. Por isso `gas_pct_of_block` em `ethereum_gas_consume` é uma **aproximação** e deve ser corrigida com dados do batch Etherscan (ver [TODO-P04](#todo-p04--enriquecer-silver-com-gas_used-e-receipt_status-do-etherscan)).

### 1.6 Tipagem EIP-2718 & Access List

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `type` | string | `tx_type` | ✅ propagar | Tipo EIP-2718: `"0x0"` = legacy, `"0x1"` = EIP-2930 (access list), `"0x2"` = EIP-1559. |
| `accessList` | array\<string\> | `access_list` | ⚠️ Bronze only recomendado | Pares `{address, storageKeys[]}` pré-declarados (EIP-2930). Baixo valor analítico; alto custo de storage. Maioria das txs tem `accessList = []`. |

**Distribuição esperada de `type` na mainnet (2024–2025):**

| Tipo | EIP | Volume estimado |
|---|---|---|
| `"0x2"` | EIP-1559 (Berlin, 2021) | ~85–90% |
| `"0x0"` | Legacy | ~8–12% |
| `"0x1"` | EIP-2930 (access list) | ~1–3% |

### 1.7 Assinatura ECDSA — Sem Valor Analítico ⚠️

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `v` | string | — | ❌ Bronze only | Componente recovery da assinatura ECDSA. Em EIP-155: `v = chain_id * 2 + 35/36`. Sem valor analítico após `from_address` recuperado. |
| `r` | string | — | ❌ Bronze only | Componente R da assinatura ECDSA (32 bytes). Sem valor analítico direto. |
| `s` | string | — | ❌ Bronze only | Componente S da assinatura ECDSA (32 bytes). EIP-2 limita `s ≤ n/2` (anti-maleabilidade). Sem valor analítico. |

> `v`, `r`, `s` são os blocos criptográficos usados para recuperar `from_address` via `ecrecover`. Com o endereço já disponível no stream, esses 3 campos não precisam propagar para Silver. Candidatos prioritários à exclusão do schema Silver.

### 1.8 Metadados de Ingestão

| Campo Bronze | Tipo | Alias Silver | Decisão Silver | Descrição |
|---|---|---|---|---|
| `_ingested_at` | timestamp | `_ingested_at` | ✅ propagar | Adicionado pelo Auto Loader. Deriva a partição `dat_ref`. Diferença `_ingested_at - tx_timestamp` = latência do pipeline. |
| `dat_ref` | date | `dat_ref` | ✅ propagar (partição) | Derivado de `to_date(_ingested_at)`. Chave de partição Delta. **Divergência**: nomes `dat_ref` (pipeline novo) vs `event_date` (DDL legado). |

### Resumo — Tabela de Classificação Completa

| Campo Bronze | Alias Silver | Categoria | Propagar para Silver? |
|---|---|---|---|
| `hash` | `tx_hash` | Identidade | ✅ |
| `blockNumber` | `block_number` | Identidade | ✅ |
| `blockHash` | `block_hash` | Identidade | ✅ |
| `transactionIndex` | `transaction_index` | Identidade | ✅ |
| `from` | `from_address` | Endereços | ✅ |
| `to` | `to_address` | Endereços | ✅ |
| `value` | `value` | Valor | ✅ (STRING) |
| `input` | `input` | Calldata | ✅ |
| `gas` | `gas` | Gas Economics | ✅ (STRING, com ressalva) |
| `gasPrice` | `gas_price` | Gas Economics | ✅ (STRING) |
| `nonce` | `nonce` | Contexto | ⚠️ Silver opcional |
| `type` | `tx_type` | Tipagem | ✅ |
| `accessList` | `access_list` | Tipagem | ❌ Bronze only |
| `v` | — | Criptografia | ❌ Bronze only |
| `r` | — | Criptografia | ❌ Bronze only |
| `s` | — | Criptografia | ❌ Bronze only |
| `_ingested_at` | `_ingested_at` | Metadados | ✅ |
| `dat_ref` | `dat_ref` | Metadados | ✅ (partição) |

> **Resultado**: de 18 campos totais, **12 devem propagar**, **1 é opcional** (`nonce`), e **5 devem ficar somente na Bronze** (`v`, `r`, `s`, `accessList`, e `nonce` se desnecessário).

---

## 2. Tabela Decoded — `eth_txs_input_decoded`

### 2.1 Função no Pipeline

Produzida pelo job `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py`,
publicada no Kinesis `mainnet-transactions-decoded` → S3 → Auto Loader Bronze.

**Estratégias de decodificação em cascata:**

```
1. DynamoDB (ABICache)    → hit: decode_type = 'abi',    decode_source = 'dynamodb_cache'
2. Etherscan API          → hit: decode_type = 'abi',    decode_source = 'etherscan_api'
3. 4byte.directory        → hit: decode_type = '4byte',  decode_source = '4byte_directory'
4. Fallback sem decode    →      decode_type = 'unknown', campos method/parms = NULL
```

**Transações excluídas intencionalmente pelo decoder** (não geram registro na decoded):
- `to IS NULL` → deploys de contrato
- `input IN ('0x', '', NULL)` → transferências ETH puras

A ausência de `tx_hash` na decoded **não indica falha** — pode ser P2P ou deploy.

### 2.2 Schema Atual e Semântica de `decode_type`

| Campo | Tipo | Descrição |
|---|---|---|
| `tx_hash` | STRING | Chave de JOIN com `eth_transactions` |
| `contract_address` | STRING | Endereço do contrato chamado (= `to` da tx) |
| `method` | STRING | Nome da função ABI (ex: `transfer`, `swapExactTokensForTokens`) |
| `parms` | STRING | Parâmetros como JSON string; NULL em decode parcial |
| `decode_type` | STRING | `abi` \| `4byte` \| `unknown` |
| `_ingested_at` | TIMESTAMP | Timestamp ingestão Auto Loader |

| `decode_type` | Confiança | `method` | `parms` |
|---|---|---|---|
| `abi` | Alta | ✅ completo | ✅ completo |
| `4byte` | Média | ✅ nome only | NULL |
| `unknown` | Nenhuma | NULL | NULL |

### 2.3 Lacunas do Schema Atual

| Campo Proposto | Tipo | Justificativa |
|---|---|---|
| `method_id` | STRING | Seletor hex de 4 bytes (`0xa9059cbb`). Atualmente só derivável do campo raw `input`. Com ele na decoded, queries de seletor não precisam do campo bruto. |
| `decode_source` | STRING | Distingue `dynamodb_cache` / `etherscan_api` / `4byte_directory` / `none`. `decode_type = 'abi'` hoje não diferencia cache hit de API call. |
| `decode_confidence` | STRING | `full` (ABI+params) \| `partial` (method only) \| `none`. Mais expressivo que o enum atual. |
| `raw_selector` | STRING | `SUBSTRING(input, 1, 10)` — fallback analítico quando decode falhou. |
| `dat_ref` | DATE | **Partição ausente**: a tabela atual não tem partição, causando full-scan em queries temporais. |

### 2.4 Proposta de Renomeação

| Antes (Bronze) | Depois | Antes (Silver) | Depois |
|---|---|---|---|
| `b_ethereum.b_transactions_decoded` | `b_ethereum.eth_txs_input_decoded` | `s_apps.txs_inputs_decoded_fast` | `s_apps.eth_txs_decoded` |

---

## 3. Diagrama do Pipeline Bronze → Silver → Gold

```mermaid
flowchart TD
    subgraph Lambda["Lambda + EventBridge (hourly)"]
        L1["contracts_ingestion/handler.py\nEtherscan txlist API"]
    end

    subgraph S3["S3 — raw/"]
        B1["raw/mainnet-transactions-data/"]
        B2["raw/mainnet-transactions-decoded/"]
        B3["raw/batch/ (Etherscan hourly)"]
    end

    subgraph BronzeStreaming["Bronze — b_ethereum (streaming DLT)"]
        E1["eth_transactions\n16 campos · particionada dat_ref"]
        E2["eth_txs_input_decoded\n(atual: b_transactions_decoded)\n5 campos · sem partição"]
    end

    subgraph BronzeBatch["Bronze — b_ethereum (batch EXTERNAL)"]
        E3["popular_contracts_txs\n10 campos · particionada ingestion_date"]
    end

    subgraph Silver["Silver — s_apps"]
        S1["transactions_fast\nstreaming staging · 14 campos"]
        S2["txs_inputs_decoded_fast\nstreaming · 5 campos"]
        S3T["transactions_ethereum\nFonte da Verdade · 22 campos\ntx_status: valid|orphaned|unconfirmed"]
        S4["eth_blocks\n21 campos"]
        S5["eth_canonical_blocks_index\n3 campos · chain_status"]
        S6["transactions_batch\nbatch EXTERNAL · 11 campos"]
    end

    subgraph Gold["Gold — g_apps / g_network"]
        G1["g_apps.popular_contracts_ranking"]
        G2["g_apps.peer_to_peer_txs"]
        G3["g_apps.ethereum_gas_consume"]
        G4["g_apps.transactions_lambda"]
        G5["g_network.network_metrics_hourly"]
    end

    L1 -->|JSON por contrato| B3
    B3 -->|batch job Bronze→Silver| E3
    B1 -->|Auto Loader| E1
    B2 -->|Auto Loader| E2

    E1 -->|dlt.read_stream| S1
    E2 -->|dlt.read_stream| S2

    S1 -->|dlt.read_stream| S3T
    S2 -->|dlt.read static snapshot| S3T
    S4 -->|dlt.read static snapshot| S3T
    S5 -->|dlt.read static snapshot| S3T
    E3 -->|batch Silver job| S6

    S3T --> G2
    S3T --> G3
    S1 -->|count by to_address last 1h| G1
    G1 -->|JOIN contratos populares| G4
    S3T -->|JOIN popular_contracts_ranking| G4
    S4 + S1 -->|GROUP BY hour| G5
```

**Join stream-static**: `transactions_fast` é lida via `dlt.read_stream()`.
`txs_inputs_decoded_fast`, `eth_blocks` e `eth_canonical_blocks_index` são snapshots estáticos (`dlt.read()`).
Transações chegadas antes do decode disponível ficam com `method = NULL` no micro-batch corrente.

---

## 4. Diagnóstico do Modelo Atual

### 4.1 Divergência de Nomenclatura

| Conceito | Pipeline legado (`4_pipeline_ethereum.py`) | Pipeline novo (`ethereum_pipeline.py`) | DDL (`setup_ddl.py`) |
|---|---|---|---|
| Bronze tx raw | `b_ethereum.b_transactions_data` | `b_ethereum.eth_transactions` | `b_transactions_data` (legado) |
| Bronze decoded | `b_ethereum.b_transactions_decoded` | `b_ethereum.eth_txs_input_decoded` | `b_transactions_decoded` (legado) |
| Partição Silver | `event_date` | `dat_ref` | `event_date` |

**Impacto**: duas tabelas podem coexistir no Unity Catalog com dados em apenas uma delas, criando ambiguidade. Operadores sem contexto histórico não sabem qual consultar.

### 4.2 Redundância entre `transactions_fast` e `transactions_ethereum`

| Aspecto | `transactions_fast` | `transactions_ethereum` |
|---|---|---|
| Origem | Bronze tx raw (direto) | JOIN: transactions_fast + decoded + eth_blocks + canonical_index |
| Campos | 14 (tx raw + partição) | 22 (enriquecida) |
| Decoded | Não | Sim (LEFT JOIN) |
| `tx_status` | Não | Sim (`valid\|orphaned\|unconfirmed`) |
| `tx_timestamp` | Não | Sim (derivado do bloco) |
| Uso Gold atual | `popular_contracts_ranking`, `network_metrics_hourly` | `peer_to_peer_txs`, `ethereum_gas_consume`, `transactions_lambda` |

**Diagnóstico**: `transactions_fast` não é redundante — é o input do stream-static JOIN. Mas o nome `_fast` não comunica que é staging interno. Queries analíticas externas devem usar somente `transactions_ethereum`.

### 4.3 Limitações do Decoder Atual

1. **Cobertura seletiva**: cobre apenas contract interactions. Deploys e P2P ficam ausentes da decoded por design — mas não é documentado explicitamente.
2. **Latência de decoded**: no micro-batch, transações recentes podem não ter o decoded ainda disponível, resultando em `method = NULL` mesmo sendo contract interactions.
3. **`decode_type = 'unknown'` é ruidoso**: indistinguível de transações sem decoded por ausência de match (ex: contrato proprietário sem ABI pública).
4. **Ausência de `method_id`**: análise de seletor exige volta ao campo raw `input`.
5. **`parms` como JSON string não tipado**: consultas sobre parâmetros específicos requerem `FROM_JSON` com schema dinâmico — ineficiente.

### 4.4 Batch Etherscan — Campos Subaproveitados

A resposta da API Etherscan `txlist` retorna 19+ campos; o batch persiste apenas 10 na Bronze e 11 na Silver. Campos de alto valor ausentes:

| Campo Etherscan | Disponível no streaming? | No batch atual? | Valor |
|---|---|---|---|
| `gasUsed` | ❌ | ❌ Silver | **Alto ★** — gas real do receipt, não limite |
| `txreceipt_status` | ❌ | ❌ Silver | **Alto ★** — 1=sucesso, 0=revert |
| `isError` | ❌ | ❌ | **Alto ★** — flag de erro (distinto de revert) |
| `methodId` | ❌ | ❌ | Médio — seletor sem precisar do decoder |
| `functionName` | ❌ | ❌ | Médio — nome da função sem ABI |
| `contractAddress` | ❌ streaming | ❌ | Médio — endereço criado em deploys |

**Campo `input_etherscan`** em `transactions_ethereum`: sempre `NULL` (placeholder nunca populado). Confirma que o enriquecimento batch→silver foi planejado mas não implementado.

---

## 5. Proposta de Modelo Futuro

### 5.1 Renomeação das Tabelas Bronze

| Atual | Proposto | Status no pipeline novo |
|---|---|---|
| `b_ethereum.b_transactions_data` | `b_ethereum.eth_transactions` | ✅ já renomeado em `ethereum_pipeline.py` |
| `b_ethereum.b_transactions_decoded` | `b_ethereum.eth_txs_input_decoded` | ✅ já renomeado em `ethereum_pipeline.py` |

Ação pendente: atualizar DDL em `setup_ddl.py` (legado ainda usa nomes antigos).

### 5.2 Schema Alvo da Bronze Decoded

```sql
CREATE TABLE IF NOT EXISTS `{cat}`.b_ethereum.eth_txs_input_decoded (
  tx_hash           STRING    COMMENT 'Hash da transação decodificada — chave de JOIN',
  contract_address  STRING    COMMENT 'Endereço do contrato chamado (= to_address da tx)',
  method            STRING    COMMENT 'Nome do método ABI (ex: transfer, swap)',
  parms             STRING    COMMENT 'Parâmetros ABI-decoded como JSON string',
  decode_type       STRING    COMMENT 'Estratégia: abi | 4byte | unknown',
  method_id         STRING    COMMENT 'Seletor de 4 bytes hex (ex: 0xa9059cbb)',
  decode_source     STRING    COMMENT 'dynamodb_cache | etherscan_api | 4byte_directory | none',
  decode_confidence STRING    COMMENT 'full (ABI+params) | partial (method only) | none',
  raw_selector      STRING    COMMENT 'Primeiros 10 chars do input hex — fallback analítico',
  _ingested_at      TIMESTAMP COMMENT 'Timestamp de ingestão Auto Loader (UTC)',
  dat_ref           DATE      COMMENT 'Partição temporal derivada de _ingested_at'
)
PARTITIONED BY (dat_ref)
TBLPROPERTIES ('quality' = 'bronze', 'pipelines.autoOptimize.managed' = 'true')
```

### 5.3 Silver Fonte da Verdade — Schema Alvo de `transactions_ethereum`

```sql
CREATE TABLE IF NOT EXISTS `{cat}`.s_apps.transactions_ethereum (
  -- Identidade
  tx_hash              STRING    COMMENT 'Hash único da transação — chave natural',
  block_number         BIGINT    COMMENT 'Número do bloco',
  block_hash           STRING    COMMENT 'Hash do bloco — necessário para canonicidade',
  transaction_index    BIGINT    COMMENT 'Posição 0-based da tx no bloco',
  -- Endereços
  from_address         STRING    COMMENT 'EOA remetente',
  to_address           STRING    COMMENT 'Destino: contrato, EOA ou NULL em deploys',
  -- Valor
  value                STRING    COMMENT 'Valor em Wei como string',
  -- Calldata
  input                STRING    COMMENT 'Calldata hex (seletor + ABI params)',
  -- Gas
  gas                  STRING    COMMENT 'Gas limit definido pelo remetente',
  gas_price            STRING    COMMENT 'Gas price em Wei',
  gas_used             BIGINT    COMMENT 'Gas efetivamente consumido (receipt batch Etherscan); NULL se indisponível',
  -- Tipo
  tx_type              STRING    COMMENT '0x0 | 0x1 | 0x2 (EIP-2718)',
  -- Contexto de bloco
  tx_timestamp         TIMESTAMP COMMENT 'Timestamp derivado do bloco',
  block_gas_limit      BIGINT    COMMENT 'Gas limit do bloco',
  block_gas_used       BIGINT    COMMENT 'Gas total consumido no bloco',
  base_fee_per_gas     STRING    COMMENT 'EIP-1559: taxa base por gas em Wei',
  -- Decoded enrichment (nullable — contract interactions somente)
  contract_address     STRING    COMMENT 'Endereço do contrato; NULL se P2P/deploy/decode ausente',
  method               STRING    COMMENT 'Nome do método ABI; NULL se indisponível',
  method_id            STRING    COMMENT 'Seletor 4 bytes (0xa9059cbb); NULL se input vazio ou deploy',
  parms                STRING    COMMENT 'Parâmetros como JSON string; NULL se decode parcial/ausente',
  decode_type          STRING    COMMENT 'abi | 4byte | unknown | NULL',
  decode_source        STRING    COMMENT 'dynamodb_cache | etherscan_api | 4byte_directory | none | NULL',
  -- Receipt enrichment (batch Etherscan — nullable)
  receipt_status       BIGINT    COMMENT '1=sucesso, 0=revert, NULL se indisponível',
  is_error             BIGINT    COMMENT '0=ok, 1=erro Etherscan, NULL se indisponível',
  -- Classificação semântica derivada
  tx_type_semantic     STRING    COMMENT 'peer_to_peer | contract_interaction | contract_deploy | unknown',
  -- Canonicidade
  tx_status            STRING    COMMENT 'valid | orphaned | unconfirmed',
  -- Metadados
  _ingested_at         TIMESTAMP COMMENT 'Timestamp de ingestão original',
  dat_ref              DATE      COMMENT 'Chave de partição Delta'
)
PARTITIONED BY (dat_ref)
TBLPROPERTIES ('quality' = 'silver', 'pipelines.autoOptimize.managed' = 'true')
```

**Campos removidos vs schema atual**: `nonce` (baixo valor), `input_etherscan` (placeholder nunca populado).
**Campos adicionados**: `gas_used`, `receipt_status`, `is_error`, `method_id`, `decode_source`, `tx_type_semantic`.

### 5.4 Classificação Semântica — `tx_type_semantic`

```python
tx_type_semantic = (
    F.when(
        F.col("to_address").isNull() &
        F.col("input").isNotNull() &
        (F.col("input") != "") & (F.col("input") != "0x"),
        F.lit("contract_deploy"),
    ).when(
        F.col("input").isNull() |
        (F.col("input") == "") | (F.col("input") == "0x"),
        F.lit("peer_to_peer"),
    ).when(
        F.col("to_address").isNotNull() &
        F.col("input").isNotNull() &
        (F.col("input") != "") & (F.col("input") != "0x"),
        F.lit("contract_interaction"),
    ).otherwise(F.lit("unknown"))
)
```

| `to_address` | `input` | Classificação | Frequência estimada |
|---|---|---|---|
| NULL | não vazio | `contract_deploy` | < 0,1% |
| não NULL | vazio / `0x` / NULL | `peer_to_peer` | ~5–10% |
| não NULL | não vazio | `contract_interaction` | ~90% |
| NULL | vazio | `unknown` | ≈ 0 (inválido) |

### 5.5 Batch Etherscan — Decisão Arquitetural

**Recomendação**: manter o fluxo batch com escopo atual (contratos populares), mas ampliar o schema para capturar os campos de alto valor hoje ignorados: `gasUsed`, `txreceipt_status`, `isError`, `methodId`, `functionName`.

O enriquecimento é aplicado na Silver via LEFT JOIN por `tx_hash` entre `transactions_ethereum` (streaming) e uma tabela de enriquecimento batch. Isso supre a lacuna crítica de `gas_used` real sem mudar a arquitetura Lambda.

---

## 6. Casos de Uso Gold

### UC1. Gas Real por Tipo de Transação — `g_apps.gas_by_tx_type` ★

**Motivação**: corrigir a imprecisão atual de `ethereum_gas_consume` que usa `gas` (limite) como proxy. Com `gas_used` real do batch Etherscan, calcula-se fee efetivo por tipo.

**Fonte**: `s_apps.transactions_ethereum` (com `gas_used` de enriquecimento batch)

```sql
SELECT
    date_trunc('hour', tx_timestamp)                   AS hour_bucket,
    tx_type_semantic,
    COUNT(*)                                           AS tx_count,
    AVG(gas_used)                                      AS avg_gas_used,
    PERCENTILE(gas_used, 0.5)                          AS p50_gas_used,
    PERCENTILE(gas_used, 0.95)                         AS p95_gas_used,
    AVG(CAST(gas_price AS DOUBLE) / 1e9)               AS avg_gas_price_gwei,
    AVG(gas_used * CAST(gas_price AS DOUBLE)) / 1e18   AS avg_fee_eth,
    SUM(gas_used * CAST(gas_price AS DOUBLE)) / 1e18   AS total_fees_eth,
    current_timestamp()                                AS computed_at
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid' AND gas_used IS NOT NULL
GROUP BY 1, 2
```

**Target**: `g_apps.gas_by_tx_type` · **Prioridade**: Alta (requer TODO-P04)

---

### UC2. Distribuição de Gas Price por Hora — `g_network.gas_price_distribution_hourly`

**Motivação**: percentis P25–P95 são mais robustos que médias simples para séries com outliers MEV com `gasPrice` extremo.

**Fonte**: `s_apps.transactions_ethereum`

```sql
SELECT
    date_trunc('hour', tx_timestamp)                         AS hour_bucket,
    COUNT(*)                                                 AS tx_count,
    PERCENTILE(CAST(gas_price AS DOUBLE) / 1e9, 0.25)       AS p25_gwei,
    PERCENTILE(CAST(gas_price AS DOUBLE) / 1e9, 0.50)       AS p50_gwei,
    PERCENTILE(CAST(gas_price AS DOUBLE) / 1e9, 0.75)       AS p75_gwei,
    PERCENTILE(CAST(gas_price AS DOUBLE) / 1e9, 0.95)       AS p95_gwei,
    current_timestamp()                                      AS computed_at
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid'
GROUP BY 1
```

**Target**: `g_network.gas_price_distribution_hourly` · **Prioridade**: Alta

---

### UC3. Métricas de Transferência P2P — `g_network.p2p_transfer_metrics_hourly`

**Motivação**: ampliar `peer_to_peer_txs` com `value_eth` derivado e métricas de volume horário.

**Fonte**: `s_apps.transactions_ethereum`

```sql
SELECT
    date_trunc('hour', tx_timestamp)       AS hour_bucket,
    COUNT(*)                               AS tx_count,
    SUM(CAST(value AS DOUBLE) / 1e18)      AS total_eth_transferred,
    AVG(CAST(value AS DOUBLE) / 1e18)      AS avg_eth_per_tx,
    MAX(CAST(value AS DOUBLE) / 1e18)      AS max_eth_single_tx,
    COUNT(DISTINCT from_address)           AS unique_senders,
    COUNT(DISTINCT to_address)             AS unique_receivers,
    current_timestamp()                    AS computed_at
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid'
  AND tx_type_semantic = 'peer_to_peer'
  AND CAST(value AS DOUBLE) > 0
GROUP BY 1
```

**Target**: `g_network.p2p_transfer_metrics_hourly` · **Prioridade**: Alta

---

### UC4. Ranking de Métodos por Contrato — `g_apps.contract_method_activity`

**Motivação**: identificar quais funções ABI são mais chamadas por contrato — revela padrões de uso de protocolos DeFi/NFT.

**Fonte**: `s_apps.transactions_ethereum`

```sql
SELECT
    date_trunc('hour', tx_timestamp)    AS hour_bucket,
    contract_address,
    method,
    method_id,
    decode_type,
    COUNT(*)                            AS call_count,
    COUNT(DISTINCT from_address)        AS unique_callers,
    SUM(CAST(value AS DOUBLE) / 1e18)  AS total_eth_sent,
    current_timestamp()                 AS computed_at
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid'
  AND tx_type_semantic = 'contract_interaction'
  AND method IS NOT NULL
GROUP BY 1, 2, 3, 4, 5
```

**Target**: `g_apps.contract_method_activity` · **Prioridade**: Média

---

### UC5. Monitoramento de Deploys de Contratos — `g_apps.contract_deploy_metrics_hourly`

**Motivação**: picos de deploy correlacionam com lançamentos de protocolos e ataques via exploit. Deploys são as txs mais custosas em gas.

**Fonte**: `s_apps.transactions_ethereum`

```sql
SELECT
    date_trunc('hour', tx_timestamp)                           AS hour_bucket,
    COUNT(*)                                                   AS deploy_count,
    COUNT(DISTINCT from_address)                               AS unique_deployers,
    AVG(CAST(gas AS DOUBLE))                                   AS avg_gas_limit,
    SUM(CASE WHEN receipt_status = 1 THEN 1 ELSE 0 END)        AS successful_deploys,
    SUM(CASE WHEN receipt_status = 0 THEN 1 ELSE 0 END)        AS failed_deploys,
    current_timestamp()                                        AS computed_at
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid'
  AND tx_type_semantic = 'contract_deploy'
GROUP BY 1
```

**Target**: `g_apps.contract_deploy_metrics_hourly` · **Prioridade**: Média

---

### UC6. Taxa de Revert por Tipo — `g_apps.tx_success_rate_hourly`

**Motivação**: transações que revertem ainda pagam gas. Taxa de revert alta em um contrato indica bug, gas insuficiente ou slippage. Requer `receipt_status` do batch Etherscan.

**Fonte**: `s_apps.transactions_ethereum`

```sql
SELECT
    date_trunc('hour', tx_timestamp)                              AS hour_bucket,
    tx_type_semantic,
    COUNT(*)                                                      AS tx_count,
    SUM(CASE WHEN receipt_status = 1 THEN 1 ELSE 0 END)           AS success_count,
    SUM(CASE WHEN receipt_status = 0 THEN 1 ELSE 0 END)           AS revert_count,
    ROUND(SUM(CASE WHEN receipt_status = 0 THEN 1 ELSE 0 END)
          * 100.0 / NULLIF(COUNT(*), 0), 2)                       AS revert_rate_pct,
    current_timestamp()                                           AS computed_at
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid' AND receipt_status IS NOT NULL
GROUP BY 1, 2
```

**Target**: `g_apps.tx_success_rate_hourly` · **Prioridade**: Alta (requer TODO-P04)

---

### UC7. Ranking de Contratos por Volume (7d) — `g_apps.contract_volume_ranking`

**Motivação**: `popular_contracts_ranking` é horária. Um ranking semanal com usuários únicos e volume ETH identificar protocolos dominantes.

```sql
SELECT
    to_address                                AS contract_address,
    method,
    COUNT(*)                                  AS call_count,
    COUNT(DISTINCT from_address)              AS unique_users,
    SUM(CAST(value AS DOUBLE) / 1e18)        AS total_eth_volume,
    MIN(tx_timestamp)                         AS first_interaction,
    MAX(tx_timestamp)                         AS last_interaction,
    CURRENT_DATE()                            AS reference_date
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid'
  AND tx_type_semantic = 'contract_interaction'
  AND dat_ref >= CURRENT_DATE() - INTERVAL 7 DAYS
GROUP BY to_address, method
ORDER BY call_count DESC
LIMIT 500
```

**Target**: `g_apps.contract_volume_ranking` · **Prioridade**: Média

---

### UC8. Elasticidade Fee × Segmento — Analítica Ad-Hoc

**Motivação**: em períodos de alta `base_fee_per_gas`, txs P2P (sensíveis a custo) diminuem enquanto DeFi/MEV se mantém. A correlação revela elasticidade de demanda por segmento.

```sql
WITH mix AS (
    SELECT date_trunc('hour', tx_timestamp) AS h, tx_type_semantic, COUNT(*) AS cnt
    FROM dev.s_apps.transactions_ethereum
    WHERE tx_status = 'valid'
    GROUP BY 1, 2
),
fees AS (
    SELECT date_trunc('hour', block_time) AS h,
           AVG(CAST(base_fee_per_gas AS DOUBLE) / 1e9) AS avg_base_fee_gwei
    FROM dev.s_apps.eth_blocks GROUP BY 1
)
SELECT m.h AS hour_bucket, m.tx_type_semantic, m.cnt AS tx_count, f.avg_base_fee_gwei
FROM mix m JOIN fees f ON m.h = f.h
ORDER BY m.h, m.tx_type_semantic
```

**Uso**: correlação Pearson entre `avg_base_fee_gwei` e `tx_count` por segmento.
**Target**: analítica ad-hoc / extensão de `g_network.network_metrics_hourly`

---

### Resumo dos Casos de Uso Gold

| ID | Tabela Target | Fonte | Requer novo dado? | Prioridade |
|---|---|---|---|---|
| UC1 | `g_apps.gas_by_tx_type` | `transactions_ethereum` | `gas_used` batch (TODO-P04) | Alta |
| UC2 | `g_network.gas_price_distribution_hourly` | `transactions_ethereum` | Não | Alta |
| UC3 | `g_network.p2p_transfer_metrics_hourly` | `transactions_ethereum` | Não | Alta |
| UC4 | `g_apps.contract_method_activity` | `transactions_ethereum` | `method_id` (TODO-P03) | Média |
| UC5 | `g_apps.contract_deploy_metrics_hourly` | `transactions_ethereum` | Não | Média |
| UC6 | `g_apps.tx_success_rate_hourly` | `transactions_ethereum` | `receipt_status` batch (TODO-P04) | Alta |
| UC7 | `g_apps.contract_volume_ranking` | `transactions_ethereum` | `method_id` (TODO-P03) | Média |
| UC8 | Ad-hoc / extensão `network_metrics_hourly` | `transactions_ethereum` + `eth_blocks` | Não | Baixa |

---

## 7. TODOs Detalhados e Sequenciados

### TODO-P01 — Auditar e Consolidar Nomenclatura das Tabelas Bronze

**Objetivo**: eliminar ambiguidade entre nomes legados e desejados.

**Passos**:
1. Executar `SHOW TABLES IN dev.b_ethereum` e confirmar coexistência de tabelas.
2. Executar `DESCRIBE EXTENDED dev.b_ethereum.eth_transactions` — verificar `Location` e `Last Modified`.
3. Atualizar DDL em `apps/dabs/src/batch/ddl/setup_ddl.py` e `apps/dabs/job_ddl_setup/src/dd_chain_explorer/ddl/setup_ddl.py`:
   - `b_transactions_data` → `eth_transactions`
   - `b_transactions_decoded` → `eth_txs_input_decoded`
4. Adicionar `dat_ref DATE PARTITIONED BY (dat_ref)` à `eth_txs_input_decoded`.
5. Confirmar que `ethereum_pipeline.py` já usa os nomes corretos.
6. Deprecar/dropar tabelas com nomes legados após confirmação.

**Checkpoint**:
```sql
DESCRIBE EXTENDED dev.b_ethereum.eth_transactions;
DESCRIBE EXTENDED dev.b_ethereum.eth_txs_input_decoded;
```

---

### TODO-P02 — Adicionar `tx_type_semantic` na Silver `transactions_ethereum`

**Objetivo**: classificar semanticamente todas as transações na Silver.

**Passos**:
1. Adicionar a expressão de classificação (ver [Seção 5.4](#54-classificação-semântica--tx_type_semantic)) em `silver_transactions_ethereum()` em `ethereum_pipeline.py`.
2. Adicionar o campo na DDL `setup_ddl.py` — tabela `s_apps.transactions_ethereum`.
3. Atualizar as Gold tables que derivam `type_transaction` localmente (`ethereum_gas_consume`, `peer_to_peer_txs`) para usar `tx_type_semantic`.

**Checkpoint**:
```sql
SELECT tx_type_semantic, COUNT(*) AS cnt
FROM dev.s_apps.transactions_ethereum
WHERE tx_status = 'valid'
GROUP BY tx_type_semantic;
-- Esperado: peer_to_peer, contract_interaction, contract_deploy, (unknown raro)
```

---

### TODO-P03 — Ampliar Schema Decoded com `method_id` e `decode_source`

**Objetivo**: adicionar `method_id`, `decode_source`, `decode_confidence`, `raw_selector` ao decoder e ao schema Bronze/Silver.

**Passos**:
1. Modificar `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py`:
   - Extrair `method_id = input[:10]` (4 bytes hex)
   - Adicionar `decode_source` por estratégia usada
   - Mapear `decode_confidence` a partir de `decode_type`
2. Atualizar payload Kinesis com os novos campos.
3. Atualizar DDL Bronze `eth_txs_input_decoded` (ver schema [Seção 5.2](#52-schema-alvo-da-bronze-decoded)).
4. Atualizar `silver_txs_inputs_decoded_fast()` para propagar novos campos.
5. Adicionar `method_id` e `decode_source` à Silver `transactions_ethereum`.

**Checkpoint**:
```sql
SELECT decode_source, decode_type, COUNT(*) AS cnt
FROM dev.b_ethereum.eth_txs_input_decoded
GROUP BY decode_source, decode_type;
```

---

### TODO-P04 — Enriquecer Silver com `gas_used` e `receipt_status` do Etherscan

**Objetivo**: trazer `gasUsed`, `txreceipt_status`, `isError`, `methodId`, `functionName` do batch Etherscan para a Silver, viabilizando UC1, UC5 e UC6.

**Passos**:
1. Ampliar schema Bronze `b_ethereum.popular_contracts_txs` para incluir os campos acima.
2. Atualizar `contracts_ingestion/handler.py` para persistir esses campos no JSON gravado no S3.
3. Atualizar o job batch Bronze→Silver para mapear `receipt_status`, `gas_used`, `is_error`.
4. Adicionar tabela de enriquecimento batch ou usar `transactions_batch` como lookup.
5. Implementar LEFT JOIN por `tx_hash` em `transactions_ethereum` ou como job periódico de backfill.
6. Remover o placeholder `input_etherscan` (nunca populado) do schema Silver.

**Checkpoint**:
```sql
SELECT COUNT(*) AS total,
       SUM(CASE WHEN receipt_status IS NOT NULL THEN 1 ELSE 0 END) AS enriched,
       SUM(CASE WHEN gas_used IS NOT NULL THEN 1 ELSE 0 END) AS has_gas_used
FROM dev.s_apps.transactions_ethereum
WHERE dat_ref = CURRENT_DATE() - 1;
```

---

### TODO-P05 — Implementar Gold Tables UC2, UC3, UC4, UC5, UC7

**Objetivo**: criar as MVs Gold não existentes identificadas nos casos de uso.

**Passos** (por MV):
1. `g_network.gas_price_distribution_hourly` — nova MV, fonte `transactions_ethereum`
2. `g_network.p2p_transfer_metrics_hourly` — nova MV, fonte `transactions_ethereum`
3. `g_apps.contract_method_activity` — nova MV, fonte `transactions_ethereum`
4. `g_apps.contract_deploy_metrics_hourly` — nova MV, fonte `transactions_ethereum`
5. `g_apps.contract_volume_ranking` — nova MV rolling 7d

Para cada MV:
- Adicionar `@dlt.table` em `ethereum_pipeline.py`
- Adicionar DDL em `setup_ddl.py`
- Adicionar tabela a `OPTIMIZE_TARGETS` em `optimize_gold.py`
- Adicionar tabela a `VACUUM_TARGETS` em `vacuum.py`

---

### TODO-P06 — Renomear `transactions_fast` para Comunicar seu Papel

**Objetivo**: tornar explícito que `transactions_fast` é staging interno do pipeline DLT,
não uma fonte analítica.

**Opção A**: renomear para `s_apps.eth_transactions_staging` — comunica que é dado bruto/intermediário.
**Opção B**: manter nome mas adicionar comentário `COMMENT 'Silver: staging interno — use transactions_ethereum para queries analíticas.'` e bloquear acesso externo via GRANT seletivo.

**Recomendação**: Opção B é menos invasiva (não requer full-refresh do pipeline).

---

### TODO-P07 — Unificar Nomes de Partição (`dat_ref` vs `event_date`)

**Objetivo**: eliminar divergência entre `dat_ref` (pipeline novo) e `event_date` (DDL legado).

**Ação**: padronizar para `dat_ref` em todos os schemas DDL e verificar que nenhuma query analítica usa `event_date` diretamente.

---

## 8. Validação do Estado Real — Queries Databricks

As queries abaixo devem ser executadas no workspace Databricks (`dev` catalog) para
validar o estado atual antes de implementar as mudanças propostas.

### 8.1 Inventário de Tabelas Bronze

```sql
-- Verificar quais tabelas bronze existem e qual está ativa
SHOW TABLES IN dev.b_ethereum;

-- Confirmar tabela ativa e localização S3
DESCRIBE EXTENDED dev.b_ethereum.eth_transactions;
DESCRIBE EXTENDED dev.b_ethereum.b_transactions_data;  -- deve estar deprecated/vazia

-- Recência dos dados (última ingestão)
SELECT MAX(_ingested_at) AS last_ingested, COUNT(*) AS total_rows
FROM dev.b_ethereum.eth_transactions;
```

### 8.2 Distribuição de Tipos de Transação (Bronze)

```sql
-- Distribuição de type EIP-2718
SELECT type AS tx_type, COUNT(*) AS cnt,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM dev.b_ethereum.eth_transactions
WHERE dat_ref >= CURRENT_DATE() - 7
GROUP BY type ORDER BY cnt DESC;

-- Classificação por to/input
SELECT
    CASE
        WHEN to IS NULL AND input NOT IN ('', '0x') AND input IS NOT NULL THEN 'contract_deploy'
        WHEN input IS NULL OR input = '' OR input = '0x' THEN 'peer_to_peer'
        ELSE 'contract_interaction'
    END AS tx_type_semantic,
    COUNT(*) AS cnt
FROM dev.b_ethereum.eth_transactions
WHERE dat_ref >= CURRENT_DATE() - 7
GROUP BY 1;
```

### 8.3 Cobertura do Decoder

```sql
-- Proporção de contract interactions com decode disponível
WITH txs AS (
    SELECT tx_hash,
        CASE WHEN input IS NULL OR input = '' OR input = '0x' THEN 'non_contract'
             WHEN to IS NULL THEN 'deploy'
             ELSE 'contract_interaction' END AS semantic_type
    FROM dev.b_ethereum.eth_transactions
    WHERE dat_ref = CURRENT_DATE() - 1
),
decoded AS (
    SELECT tx_hash, decode_type
    FROM dev.b_ethereum.eth_txs_input_decoded
    WHERE dat_ref = CURRENT_DATE() - 1
)
SELECT t.semantic_type, d.decode_type,
       COUNT(*) AS cnt,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY t.semantic_type), 2) AS pct
FROM txs t LEFT JOIN decoded d ON t.tx_hash = d.tx_hash
GROUP BY t.semantic_type, d.decode_type
ORDER BY t.semantic_type, cnt DESC;
```

### 8.4 Validação da Silver `transactions_ethereum`

```sql
-- Distribuição de tx_status
SELECT tx_status, COUNT(*) AS cnt
FROM dev.s_apps.transactions_ethereum
WHERE dat_ref = CURRENT_DATE() - 1
GROUP BY tx_status;

-- Cobertura do decoded na Silver
SELECT
    SUM(CASE WHEN method IS NOT NULL THEN 1 ELSE 0 END)     AS decoded_count,
    SUM(CASE WHEN method IS NULL THEN 1 ELSE 0 END)         AS not_decoded_count,
    COUNT(*)                                                  AS total,
    ROUND(SUM(CASE WHEN method IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS decode_coverage_pct
FROM dev.s_apps.transactions_ethereum
WHERE dat_ref = CURRENT_DATE() - 1
  AND tx_status = 'valid';

-- Verificar campo receipt_status (deve ser NULL enquanto TODO-P04 não implementado)
SELECT
    SUM(CASE WHEN receipt_status IS NOT NULL THEN 1 ELSE 0 END) AS has_receipt_status,
    SUM(CASE WHEN input_etherscan IS NOT NULL THEN 1 ELSE 0 END) AS has_input_etherscan
FROM dev.s_apps.transactions_ethereum
WHERE dat_ref = CURRENT_DATE() - 1;
```

### 8.5 Validação do Batch Etherscan

```sql
-- Recência e volume do batch
SELECT ingestion_date, COUNT(*) AS tx_count, COUNT(DISTINCT contract_address) AS contracts
FROM dev.b_ethereum.popular_contracts_txs
GROUP BY ingestion_date ORDER BY ingestion_date DESC LIMIT 10;

-- Confirmar ausência de gas_used na bronze batch (antes do TODO-P04)
DESCRIBE dev.b_ethereum.popular_contracts_txs;

-- Verificar sobreposição streaming × batch por tx_hash
SELECT COUNT(*) AS overlap_count
FROM dev.s_apps.transactions_ethereum te
JOIN dev.s_apps.transactions_batch tb ON te.tx_hash = tb.tx_hash
WHERE te.dat_ref = CURRENT_DATE() - 1;
```

### 8.6 Validação da API Etherscan

```bash
# Verificar resposta real da API e confirmar campos disponíveis
curl "https://api.etherscan.io/api?module=account&action=txlist\
&address=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48\
&startblock=0&endblock=99999999&page=1&offset=3&sort=desc\
&apikey=YOUR_API_KEY" | python3 -m json.tool

# Campos esperados na resposta:
# blockNumber, blockHash, timeStamp, hash, nonce, transactionIndex,
# from, to, value, gas, gasPrice, input,
# methodId, functionName,              ← relevantes para UC4
# contractAddress,                     ← relevante para deploys
# cumulativeGasUsed, gasUsed,          ← relevantes para UC1, UC6
# txreceipt_status, isError,           ← relevantes para UC6
# confirmations
```

---

## 9. Referências de Arquivos

| Escopo | Caminho |
|---|---|
| Pipeline DLT ativo | `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py` |
| Pipeline DLT legado | `apps/dabs/src/streaming/4_pipeline_ethereum.py` |
| DDL principal | `apps/dabs/src/batch/ddl/setup_ddl.py` |
| DDL job dedicado | `apps/dabs/job_ddl_setup/src/dd_chain_explorer/ddl/setup_ddl.py` |
| Job decoder | `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py` |
| Lambda batch Etherscan | `apps/lambda/contracts_ingestion/handler.py` |
| Maintenance vacuum | `apps/dabs/job_delta_maintenance/src/batch/dm_delta_maintenance/vacuum.py` |
| Maintenance optimize gold | `apps/dabs/job_delta_maintenance/src/batch/dm_delta_maintenance/optimize_gold.py` |
| Análise de blocos (referência) | `docs/analysis/analisys_block_data.md` |
| Arquitetura data processing | `docs/architecture/03_data_processing.md` |
| **Docs Ethereum — Transactions** | https://ethereum.org/developers/docs/transactions/ |
| **Docs Etherscan — txlist** | https://docs.etherscan.io/api-reference/endpoint/txlist |
| **EIP-1559 (dynamic fee)** | https://eips.ethereum.org/EIPS/eip-1559 |
| **EIP-2930 (access list)** | https://eips.ethereum.org/EIPS/eip-2930 |
| **4byte.directory** | https://www.4byte.directory/signatures/ |
