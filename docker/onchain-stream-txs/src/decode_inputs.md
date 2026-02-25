# Transaction Input Decoder — Estratégia de Decode

## Visão Geral

O Job 5 (`5_txs_input_decoder.py`) consome transações do tópico Kafka
`mainnet.4.transactions.data`, decodifica o campo `input` de cada transação
(chamadas a contratos) e publica o resultado em
`mainnet.5.transactions.input_decoded`.

Este documento descreve a estratégia de decode otimizada, incluindo:
- Cache de ABIs persistente no Redis (DB 6)
- Rotação de múltiplas chaves Etherscan (6 API keys via SSM)
- Fallback para 4byte.directory
- Pipeline interno de decode

---

## Arquitetura

```
┌──────────────────┐     ┌──────────────────────────────────────┐     ┌────────────────────────┐
│  Kafka Consumer  │────▶│   TransactionInputDecoder            │────▶│   Kafka Producer       │
│  topic: 4.txs    │     │                                      │     │   topic: 5.decoded     │
└──────────────────┘     │  ┌────────────┐  ┌────────────────┐  │     └────────────────────────┘
                         │  │  ABICache   │  │ EtherscanMulti │  │
                         │  │ (Redis DB6) │  │ (6 API keys)   │  │
                         │  └─────┬──────┘  └──────┬─────────┘  │
                         │        │                 │            │
                         │        ▼                 ▼            │
                         │  ┌─────────────────────────────────┐  │
                         │  │     Decode Pipeline              │  │
                         │  │  1. Redis cache hit → full       │  │
                         │  │  2. Etherscan API   → full       │  │
                         │  │  3. 4byte.directory → partial    │  │
                         │  │  4. Raw selector    → unknown    │  │
                         │  └─────────────────────────────────┘  │
                         └──────────────────────────────────────┘
```

---

## 1. Cache de ABIs — Redis DB 6

### Por que Redis ao invés de disco?

| Aspecto           | Disco (`/tmp/abi_cache/`)       | Redis DB 6                      |
|-------------------|---------------------------------|---------------------------------|
| Persistência      | Perdido ao reiniciar container  | Persiste entre deploys          |
| Compartilhamento  | Apenas processo local           | Acessível por todos containers  |
| Desempenho        | I/O de filesystem               | In-memory, sub-millisecond      |
| Negative cache    | Não implementado                | TTL nativo de 24h               |

### Estrutura no Redis

| Tipo    | Chave                             | Valor                | TTL      |
|---------|-----------------------------------|----------------------|----------|
| Hash    | `contract_abis`                   | `{address: abi_json}`| Sem TTL  |
| String  | `abi:nv:{address}`                | `"1"`                | 24 horas |

- **`contract_abis`** — Hash com todas as ABIs. Chave = endereço lowercase, Valor = ABI
  como JSON string. ABIs nunca mudam, então não precisa de TTL.
- **`abi:nv:{address}`** — **Negative cache**: endereços que sabemos não ter ABI
  verificada no Etherscan. TTL de 24h evita chamadas repetidas para contratos
  não verificados, mas permite re-tentativa após 24h (caso um dev verifique o
  contrato depois).

### Módulo: `utils_decode/abi_cache.py`

```python
cache = ABICache(logger)
abi = cache.get("0x1234...")          # Hit → retorna list, Miss → None
cache.put("0x1234...", abi_list)      # Armazena permanentemente
cache.mark_unverified("0x5678...")    # Negative cache (TTL 24h)
cache.is_unverified("0x5678...")      # True se está no negative cache
cache.stats()                         # {"cached_abis": N, "unverified": M}
```

---

## 2. Multi-Key Etherscan — Rotação de 6 Chaves

### Problema anterior

O decoder usava **1 única API key**, lida do SSM via `SSM_ETHERSCAN_KEY`.
O rate-limit free tier do Etherscan é **5 req/seg por chave**, insuficiente
para o volume de contratos únicos processados.

### Solução

Carregar todas as 6 chaves do SSM via `get_parameters_by_path("/etherscan-api-keys")`
e fazer round-robin com throttle individual por chave.

| Parâmetro SSM                       | Uso                      |
|--------------------------------------|--------------------------|
| `/etherscan-api-keys/api-key-1`      | Rotação round-robin      |
| `/etherscan-api-keys/api-key-2`      | Rotação round-robin      |
| `/etherscan-api-keys/api-key-3`      | Rotação round-robin      |
| `/etherscan-api-keys/api-key-4`      | Rotação round-robin      |
| `/etherscan-api-keys/api-key-5`      | Rotação round-robin      |
| `/etherscan-api-keys/api-key-6`      | Rotação round-robin      |

### Throughput

- 1 chave: 5 req/seg
- 6 chaves com round-robin: **~30 req/seg**
- Com Redis cache warm: **milhares de msg/seg** (a maioria não precisa de API call)

### Módulo: `utils_decode/etherscan_multi.py`

```python
client = MultiKeyEtherscanClient(logger, api_keys=["key1", ..., "key6"])
abi = client.fetch_contract_abi("0x1234...")   # Round-robin com throttle
sig = client.get_4byte_signature("0x38ed1739") # 4byte.directory (sem rate limit significativo)
```

---

## 3. Pipeline de Decode

Para cada transação consumida do Kafka:

```
1.  tx.to vazio?            → SKIP (contract deploy, sem input relevante)
2.  tx.input < 10 chars?    → SKIP (ETH transfer puro)
3.  ABICache.get(address)   → HIT?  → decode com ABI (full)  ✅
4.  ABICache.is_unverified? → True? → 4byte fallback         ⬇
5.  Etherscan API (rotação) → ABI?  → armazena no cache + decode (full) ✅
6.  Etherscan retornou null → mark_unverified(24h) + 4byte   ⬇
7.  4byte.directory         → sig?  → partial decode          ⚠
8.  Tudo falhou             → raw selector como method        ❌
```

### Tipos de decode no output

| `_decode_type` | Significado                                    |
|----------------|------------------------------------------------|
| `full`         | ABI encontrada, método + parâmetros tipados    |
| `partial`      | 4byte match, apenas nome do método             |
| `unknown`      | Apenas selector hex (0x + 4 bytes)             |

---

## 4. Variáveis de Ambiente

| Variável              | Descrição                                        | Default                                   |
|-----------------------|--------------------------------------------------|-------------------------------------------|
| `NETWORK`             | Rede Ethereum                                    | `mainnet`                                 |
| `KAFKA_BROKERS`       | Bootstrap servers Kafka                          | —                                         |
| `SCHEMA_REGISTRY_URL` | URL do Confluent Schema Registry                 | —                                         |
| `TOPIC_LOGS`          | Tópico de logs da aplicação                      | —                                         |
| `TOPIC_TXS_DATA`      | Tópico de input (transações raw)                 | `mainnet.4.transactions.data`             |
| `TOPIC_TXS_DECODED`   | Tópico de output (transações decoded)            | `mainnet.5.transactions.input_decoded`    |
| `CONSUMER_GROUP`       | Consumer group Kafka                             | `cg_txs_input_decoder`                   |
| `SSM_ETHERSCAN_PATH`  | Path prefix no SSM para as Etherscan API keys    | `/etherscan-api-keys`                     |
| `REDIS_HOST`          | Hostname do Redis                                | `localhost`                               |
| `REDIS_PORT`          | Porta do Redis                                   | `6379`                                    |
| `APP_ENV`             | Ambiente (`dev` / `prod`)                        | `prod`                                    |
| `UNVERIFIED_TTL`      | TTL em segundos da negative cache                | `86400` (24h)                             |

---

## 5. Estrutura de Arquivos

```
src/
├── 5_txs_input_decoder.py   ← Job principal (reescrito)
├── decode_inputs.md          ← Este documento
├── utils_decode/
│   ├── __init__.py
│   ├── abi_cache.py          ← ABICache (Redis DB6)
│   └── etherscan_multi.py    ← MultiKeyEtherscanClient (6 keys, round-robin)
└── utils/
    ├── dm_redis.py           ← DMRedis (existente, reutilizado)
    ├── dm_parameter_store.py ← ParameterStoreClient (existente, reutilizado)
    └── ...
```

---

## 6. Métricas de Progresso

O job loga a cada 500 mensagens processadas:

```
Progress — decoded: 1500, fallback: 120, skipped: 80, cache_hit: 1200, api_call: 300
```

- `decoded`: total de mensagens decoded com sucesso (full + partial + unknown)
- `fallback`: decode via 4byte ou raw selector
- `skipped`: contract deploy ou ETH transfer
- `cache_hit`: ABI encontrada no Redis (sem API call)
- `api_call`: ABI buscada via Etherscan API
