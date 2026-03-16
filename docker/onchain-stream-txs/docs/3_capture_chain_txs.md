# Captura de Transacoes On-Chain

Este documento descreve em detalhe a logica de cada job de streaming, os topicos Kafka consumidos e produzidos, o formato dos dados e as variaveis de ambiente necessarias.

---

## Fluxo Geral de Dados

O pipeline de captura e composto por 5 jobs que operam em cadeia. Cada job consome de um topico Kafka, processa os dados, e produz para o proximo topico:

```
         Ethereum mainnet (RPC)
                |
                v
  +-----------------------------+
  | Job 1: Mined Blocks Watcher |   polling a cada N segundos
  +-----------------------------+
                |
                | produz: mainnet.1.mined_blocks.events
                |
       +--------+---------+
       |                   |
       v                   v
  +-----------+    +-------------------+
  | Job 2:    |    | Job 3:            |
  | Orphan    |    | Block Data        |
  | Blocks    |    | Crawler           |
  | Watcher   |    |                   |
  +-----------+    +-------------------+
       |                   |
       | produz:           | produz:
       | mainnet.1.mined_  | mainnet.2.blocks.data
       | blocks.events     | mainnet.3.block.txs.hash_id
       | (alerta orphan)   |
       |                   v
       |           +-------------------+
       |           | Job 4:            |
       |           | Raw Transactions  |   x6 replicas
       |           | Crawler           |
       |           +-------------------+
       |                   |
       |                   | produz: mainnet.4.transactions.data
       |                   |
       |                   v
       |           +-------------------+
       |           | Job 5:            |
       |           | Transaction Input |
       |           | Decoder           |
       |           +-------------------+
       |                   |
       |                   | produz: mainnet.5.transactions.input_decoded
       |                   |
       +-------------------+-------> mainnet.0.application.logs
                                    (todos os jobs produzem logs)
```

### Topicos Kafka

| Topico | Descricao | Particoes | Schema AVRO |
|--------|-----------|-----------|-------------|
| `mainnet.0.application.logs` | Logs estruturados de todos os jobs | 1 | `0_application_logs_avro.json` |
| `mainnet.1.mined_blocks.events` | Eventos de bloco minerado ou orfao | 1 | `1_mined_block_event_schema_avro.json` |
| `mainnet.2.blocks.data` | Dados completos de cada bloco | 1 | `2_block_data_schema_avro.json` |
| `mainnet.3.block.txs.hash_id` | Hash IDs de transacoes por bloco | 8 | `3_transaction_hash_ids_schema_avro.json` |
| `mainnet.4.transactions.data` | Dados brutos de cada transacao | 8 | `4_transactions_schema_avro.json` |
| `mainnet.5.transactions.input_decoded` | Transacoes com campo `input` decodificado | 4 | `txs_contract_call_decoded.json` |

Todos os topicos utilizam serializacao AVRO com schemas registrados no Schema Registry (Confluent em DEV, AWS Glue em PROD).

---

## Job 1 -- Mined Blocks Watcher

**Script**: `1_mined_blocks_watcher.py`
**Classe**: `MinedBlocksWatcher`

### Funcao

Detecta novos blocos minerados na rede Ethereum por polling. A cada iteracao, consulta o bloco mais recente via RPC e verifica se o numero do bloco e sequencialmente o proximo em relacao ao ultimo bloco observado. Se for, emite um evento de bloco minerado.

### Logica de execucao

```
loop infinito:
  bloco_atual = web3.eth.get_block("latest")
  se bloco_atual.number == bloco_anterior + 1:
    emitir evento (block_timestamp, block_number, block_hash)
  bloco_anterior = bloco_atual.number
  sleep(CLOCK_FREQUENCY)
```

O job aceita apenas blocos sequenciais, garantindo que nenhum bloco seja pulado. A frequencia de polling e controlada por `CLOCK_FREQUENCY` (em segundos).

### Formato de saida

**Topico**: `mainnet.1.mined_blocks.events`
**Key**: `"mined"` (string fixa)
**Value**:

```json
{
  "block_timestamp": 1708612800,
  "block_number": 19283746,
  "block_hash": "a1b2c3d4..."
}
```

### Variaveis de ambiente

| Variavel | Descricao | Exemplo |
|----------|-----------|---------|
| `SSM_SECRET_NAME` | Nome do parametro SSM com a API key Alchemy | `/web3-api-keys/alchemy/api-key-1` |
| `TOPIC_LOGS` | Topico de logs | `mainnet.0.application.logs` |
| `TOPIC_MINED_BLOCKS_EVENTS` | Topico de saida | `mainnet.1.mined_blocks.events` |
| `CLOCK_FREQUENCY` | Intervalo de polling em segundos | `1` |

### Provedor Web3

Utiliza Alchemy via `Web3Handler.get_node_connection(api_key_name, 'alchemy')`.

---

## Job 2 -- Orphan Blocks Watcher

**Script**: `2_orphan_blocks_watcher.py`
**Classe**: `OrphanBlocksProcessor`

### Funcao

Detecta blocos orfaos (reorganizacoes de cadeia) comparando o hash de blocos ja confirmados com o hash armazenado em cache DynamoDB. Quando a rede Ethereum sofre uma reorganizacao, um bloco previamente aceito pode ser substituido por outro com hash diferente. Este job identifica essas situacoes.

### Logica de execucao

```
para cada evento em mainnet.1.mined_blocks.events:
  armazenar (block_number, block_hash) no DynamoDB (PK=BLOCK_CACHE, SK=block_number)
  bloco_seguro = block_number - delay_counter
  dados_bloco_seguro = web3.eth.get_block(bloco_seguro)
  hash_anterior = dynamodb.get(PK=BLOCK_CACHE, SK=bloco_seguro)

  se hash_anterior != dados_bloco_seguro.hash:
    emitir evento orphan em mainnet.1.mined_blocks.events

  (entradas antigas expiram automaticamente via TTL de 3600s)
  delay_counter = min(delay_counter + 1, NUM_CONFIRMATIONS)
```

O `delay_counter` cresce progressivamente de 0 a `NUM_CONFIRMATIONS` (padrao: 10 blocos), garantindo que apenas blocos com confirmacoes suficientes sejam avaliados.

### Formato de saida

**Topico**: `mainnet.1.mined_blocks.events` (mesmo topico do Job 1)
**Key**: `"orphan"` (diferencia de `"mined"` emitido pelo Job 1)
**Value**:

```json
{
  "block_timestamp": 1708612800,
  "block_number": 19283736,
  "block_hash": "e5f6a7b8..."
}
```

### Uso do DynamoDB

- **Entidade**: `BLOCK_CACHE` (PK=`BLOCK_CACHE`, SK=`{block_number}`)
- **Operacoes**: `put_item` para armazenar hashes (com TTL 3600s), `get_item` para comparar
- Entradas antigas expiram automaticamente via TTL (nao requer limpeza manual)
- A instancia `DMDynamoDB` e utilizada como cache de hashes de blocos

### Variaveis de ambiente

| Variavel | Descricao | Exemplo |
|----------|-----------|---------|
| `SSM_SECRET_NAME` | Parametro SSM com a API key Alchemy | `/web3-api-keys/alchemy/api-key-2` |
| `TOPIC_LOGS` | Topico de logs | `mainnet.0.application.logs` |
| `TOPIC_MINED_BLOCKS_EVENTS` | Topico de entrada e saida | `mainnet.1.mined_blocks.events` |
| `CONSUMER_GROUP_ID` | Consumer group | `cg_orphan_block_events` |
| `DYNAMODB_TABLE` | Nome da tabela DynamoDB | `dm-chain-explorer` |
| `NUM_CONFIRMATIONS` | Numero de confirmacoes para considerar um bloco seguro | `10` |

---

## Job 3 -- Block Data Crawler

**Script**: `3_block_data_crawler.py`
**Classe**: `BlockDataCrawler`

### Funcao

Consome eventos de blocos minerados e captura os dados completos de cada bloco via RPC. Produz dois tipos de dados: os dados completos do bloco e os hash IDs de todas as transacoes contidas nele.

### Logica de execucao

```
para cada evento em mainnet.1.mined_blocks.events:
  bloco_completo = web3.eth.get_block(evento.block_number)
  dados_limpos = parse_block_data(bloco_completo)

  produzir dados_limpos em mainnet.2.blocks.data

  para cada tx_hash em dados_limpos.transactions[:TXS_PER_BLOCK]:
    produzir {tx_hash} em mainnet.3.block.txs.hash_id
    (distribuir por particao: indice % num_partitions)
```

O parametro `TXS_PER_BLOCK` limita o numero de transacoes enviadas por bloco para controlar a taxa de ingestao. As transacoes sao distribuidas ciclicamente entre as 8 particoes do topico de hash IDs, permitindo consumo paralelo pelo Job 4.

### Formato de saida -- Dados de bloco

**Topico**: `mainnet.2.blocks.data`
**Key**: numero do bloco (string)
**Value**:

```json
{
  "number": 19283746,
  "timestamp": 1708612800,
  "hash": "a1b2c3d4...",
  "parentHash": "f0e1d2c3...",
  "difficulty": 0,
  "totalDifficulty": "58750000...",
  "nonce": "0000000000000000",
  "size": 12345,
  "miner": "0xAbCd...",
  "baseFeePerGas": 15000000000,
  "gasLimit": 30000000,
  "gasUsed": 12345678,
  "logsBloom": "...",
  "extraData": "...",
  "transactionsRoot": "...",
  "stateRoot": "...",
  "transactions": ["a1b2...", "c3d4...", "..."],
  "withdrawals": [{"index": 1, "...": "..."}]
}
```

### Formato de saida -- Hash IDs de transacoes

**Topico**: `mainnet.3.block.txs.hash_id`
**Key**: hash da transacao (string)
**Value**:

```json
{
  "tx_hash": "a1b2c3d4e5f6..."
}
```

### Variaveis de ambiente

| Variavel | Descricao | Exemplo |
|----------|-----------|---------|
| `SSM_SECRET_NAME` | Parametro SSM com a API key Alchemy | `/web3-api-keys/alchemy/api-key-2` |
| `TOPIC_LOGS` | Topico de logs | `mainnet.0.application.logs` |
| `TOPIC_MINED_BLOCKS_EVENTS` | Topico de entrada | `mainnet.1.mined_blocks.events` |
| `TOPIC_MINED_BLOCKS` | Topico de saida (dados de blocos) | `mainnet.2.blocks.data` |
| `TOPIC_TXS_HASH_IDS` | Topico de saida (hash IDs) | `mainnet.3.block.txs.hash_id` |
| `TOPIC_TXS_HASH_IDS_PARTITIONS` | Numero de particoes do topico hash IDs | `8` |
| `CONSUMER_GROUP` | Consumer group | `cg_block_data_crawler` |
| `TXS_PER_BLOCK` | Limite de transacoes por bloco | `50` |

---

## Job 4 -- Raw Transactions Crawler

**Script**: `4_mined_txs_crawler.py`
**Classe**: `RawTransactionsProcessor`

### Funcao

Consome hash IDs de transacoes e captura os dados brutos de cada transacao via RPC. E o job com maior demanda de throughput, pois cada bloco Ethereum pode conter centenas de transacoes. Por isso, e executado com multiplas replicas (6 em DEV, 8 em PROD).

### Logica de execucao

```
liberar API keys ociosas no semaforo
api_key = eleger api_key menos utilizada

para cada msg em mainnet.3.block.txs.hash_id:
  tx_data = web3.eth.get_transaction(msg.tx_hash)
  tx_limpa = parse_transaction_data(tx_data)
  produzir tx_limpa em mainnet.4.transactions.data

  a cada 100 transacoes:
    liberar api_key atual
    eleger nova api_key (menos utilizada, disponivel no semaforo)
    reconectar web3 com nova api_key

  a cada 10 transacoes:
    limpar api_keys ociosas do semaforo (timeout 15s)
```

O gerenciamento de API keys e detalhado em [4_api_key_management.md](4_api_key_management.md).

### Formato de saida

**Topico**: `mainnet.4.transactions.data`
**Key**: hash da transacao (string)
**Value**:

```json
{
  "blockHash": "a1b2c3d4...",
  "blockNumber": 19283746,
  "hash": "e5f6a7b8...",
  "transactionIndex": 42,
  "from": "0x1234...",
  "to": "0xABCD...",
  "value": "1000000000000000000",
  "input": "38ed1739000000...",
  "gas": 21000,
  "gasPrice": 15000000000,
  "maxFeePerGas": 20000000000,
  "maxPriorityFeePerGas": 1500000000,
  "nonce": 123,
  "v": 28,
  "r": "a1b2...",
  "s": "c3d4...",
  "type": 2,
  "accessList": []
}
```

**Observacao sobre o campo `input`**: O campo `input` e serializado sem o prefixo `0x` devido ao comportamento de `DataMasterUtils.convert_hexbytes_to_str()` (que usa `bytes.hex()`). O Job 5 normaliza esse campo adicionando o prefixo antes da decodificacao.

### Variaveis de ambiente

| Variavel | Descricao | Exemplo |
|----------|-----------|---------|
| `SSM_SECRET_NAMES` | Range compactado de API keys Infura | `/web3-api-keys/infura/api-key-1-17` |
| `TOPIC_LOGS` | Topico de logs | `mainnet.0.application.logs` |
| `TOPIC_TXS_HASH_IDS` | Topico de entrada | `mainnet.3.block.txs.hash_id` |
| `TOPIC_TXS_DATA` | Topico de saida | `mainnet.4.transactions.data` |
| `CONSUMER_GROUP` | Consumer group | `cg_mined_raw_txs` |
| `DYNAMODB_TABLE` | Nome da tabela DynamoDB | `dm-chain-explorer` |

---

## Job 5 -- Transaction Input Decoder

**Script**: `5_txs_input_decoder.py`
**Classe**: `TransactionInputDecoder`

### Funcao

Consome transacoes brutas e decodifica o campo `input` (calldata) para identificar qual funcao de contrato inteligente foi chamada e com quais parametros. Utiliza uma estrategia de decodificacao em tres niveis.

### Estrategia de decodificacao

```
para cada transacao em mainnet.4.transactions.data:
  normalizar input (adicionar prefixo 0x se ausente)
  ignorar se deploy de contrato (to == "")
  ignorar se transferencia ETH simples (input == "0x")

  selector = input[:10]   (0x + 4 bytes)

  1. Buscar ABI do contrato no Etherscan
     se ABI encontrada:
       decodificar com web3.contract.decode_function_input()
       resultado: {method: "swap(...)", parms: {...}, decode_type: "full"}

  2. Fallback: consultar 4byte.directory com o selector
     se assinatura encontrada:
       resultado: {method: "swap(...)", parms: {}, decode_type: "partial"}

  3. Ultimo recurso:
       resultado: {method: "0x38ed1739", parms: {}, decode_type: "unknown"}

  produzir resultado em mainnet.5.transactions.input_decoded
```

### Cache de ABI

O `EtherscanClient` implementa cache em disco (`/tmp/abi_cache/`) e cache em memoria (`@lru_cache`). A ABI de cada contrato e buscada no Etherscan apenas uma vez por endereco durante a vida do container.

### Formato de saida

**Topico**: `mainnet.5.transactions.input_decoded`
**Key**: hash da transacao (string)
**Value**:

```json
{
  "tx_hash": "e5f6a7b8...",
  "block_number": 19283746,
  "from": "0x1234...",
  "contract_address": "0xABCD...",
  "input": "0x38ed1739000000...",
  "method": "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
  "parms": "{\"amountIn\": 1000000, \"_decode_type\": \"full\"}"
}
```

O campo `parms` e uma string JSON que contem os parametros decodificados e um campo metadata `_decode_type` indicando o nivel de decodificacao obtido (`full`, `partial` ou `unknown`).

### Variaveis de ambiente

| Variavel | Descricao | Exemplo |
|----------|-----------|---------|
| `SSM_ETHERSCAN_KEY` | Parametro SSM com a API key Etherscan | `/etherscan-api-keys/api-key-1` |
| `TOPIC_LOGS` | Topico de logs | `mainnet.0.application.logs` |
| `TOPIC_TXS_DATA` | Topico de entrada | `mainnet.4.transactions.data` |
| `TOPIC_TXS_DECODED` | Topico de saida | `mainnet.5.transactions.input_decoded` |
| `CONSUMER_GROUP` | Consumer group | `cg_txs_input_decoder` |
| `ABI_CACHE_DIR` | Diretorio de cache de ABIs em disco | `/tmp/abi_cache` |

---

## Classe Base: ChainExtractor

Todos os jobs (exceto o Job 1) herdam de `ChainExtractor`, uma classe abstrata definida em `chain_extractor.py`:

```python
class ChainExtractor(ABC):
    @abstractmethod
    def src_config(self, src_properties) -> Self: ...
    @abstractmethod
    def sink_config(self, sink_properties) -> Self: ...
    @abstractmethod
    def run(self, callback) -> None: ...

    def consuming_topic(self, consumer) -> Generator:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg:
                yield {"key": msg.key(), "value": msg.value()}
```

O padrao `src_config` / `sink_config` / `run` permite composicao fluente:

```python
(
    BlockDataCrawler(logger)
    .src_config(src_properties)
    .sink_config(sink_properties)
    .run(callback=handler_kafka.message_handler)
)
```

---

## Serializacao AVRO e Schema Registry

Toda comunicacao entre jobs via Kafka utiliza serializacao AVRO. Os schemas estao definidos em `src/schemas/`:

| Arquivo | Usado por |
|---------|-----------|
| `0_application_logs_avro.json` | Todos os jobs (logging) |
| `1_mined_block_event_schema_avro.json` | Jobs 1, 2, 3 |
| `2_block_data_schema_avro.json` | Job 3 |
| `3_transaction_hash_ids_schema_avro.json` | Jobs 3, 4 |
| `4_transactions_schema_avro.json` | Jobs 4, 5 |
| `txs_contract_call_decoded.json` | Job 5 |

O `KafkaHandler` utiliza `confluent-kafka` com `AvroSerializer` / `AvroDeserializer` vinculados ao Schema Registry. Em DEV, schemas sao auto-registrados se ausentes. Em PROD, devem estar pre-registrados no AWS Glue Schema Registry.