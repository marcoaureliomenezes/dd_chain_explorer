# Gerenciamento de API Keys

Este documento descreve o sistema de gerenciamento de API keys utilizado pelos jobs de streaming para acessar provedores Web3 (Alchemy, Infura) e Etherscan, incluindo o mecanismo de armazenamento, eleicao distribuida, rotacao e monitoramento de consumo.

---

## Visao Geral

O pipeline de captura de transacoes depende de API keys de tres provedores:

| Provedor | Quantidade | Utilizado por | Finalidade |
|----------|-----------|---------------|------------|
| Alchemy | 4 keys | Jobs 1, 2, 3 | RPC Ethereum (blocos) |
| Infura | 17 keys | Job 4 | RPC Ethereum (transacoes) |
| Etherscan | 5 keys | Job 5 | ABI de contratos inteligentes |

As keys de Alchemy e Infura sao gerenciadas pelo sistema de semaforo distribuido descrito abaixo. As keys de Etherscan sao utilizadas diretamente via parametro SSM, sem necessidade de semaforo (Job 5 opera como instancia unica).

---

## Armazenamento no AWS SSM Parameter Store

Todas as API keys sao armazenadas como parametros do tipo `SecureString` no AWS Systems Manager Parameter Store, organizadas hierarquicamente:

```
/web3-api-keys/
    alchemy/
        api-key-1       -> wss://eth-mainnet.g.alchemy.com/v2/<TOKEN>
        api-key-2       -> wss://eth-mainnet.g.alchemy.com/v2/<TOKEN>
        api-key-3       -> wss://eth-mainnet.g.alchemy.com/v2/<TOKEN>
        api-key-4       -> wss://eth-mainnet.g.alchemy.com/v2/<TOKEN>
    infura/
        api-key-1       -> https://mainnet.infura.io/v3/<TOKEN>
        api-key-2       -> https://mainnet.infura.io/v3/<TOKEN>
        ...
        api-key-17      -> https://mainnet.infura.io/v3/<TOKEN>
/etherscan-api-keys/
    api-key-1           -> <ETHERSCAN_TOKEN>
    api-key-2           -> <ETHERSCAN_TOKEN>
    ...
    api-key-5           -> <ETHERSCAN_TOKEN>
```

O acesso ao SSM e mediado pelo modulo `dm_parameter_store.py`, que encapsula o cliente `boto3` SSM com operacoes `get_parameter()`, `put_parameter()`, `delete_parameter()`, `list_parameters()` e `get_parameters_by_path()`.

---

## Semaforo Distribuido com Redis

O Job 4 (Raw Transactions Crawler) opera com multiplas replicas simultaneas (6 em DEV, 8 em PROD), cada uma necessitando de uma API key exclusiva. Para evitar que duas replicas utilizem a mesma key simultaneamente, o modulo `api_keys_manager.py` implementa um mecanismo de semaforo distribuido sobre o Redis.

### Databases Redis utilizadas

| Database | Finalidade |
|----------|------------|
| `db=0` | **Semaforo**: rastreia qual replica detem qual API key |
| `db=1` | **Contador**: acumula o numero total de requisicoes feitas com cada key |
| `db=2` | Cache de hashes de blocos (usado pelo Job 2) |
| `db=3` | Snapshot de estado para monitoramento |

### Notacao compactada de API keys

As variaveis de ambiente dos jobs utilizam notacao compactada para referencias conjuntos de API keys. O metodo `_decompress_api_key_names()` expande essa notacao:

```
Entrada:  "/web3-api-keys/infura/api-key-1-17"
Saida:    ["/web3-api-keys/infura/api-key-1",
           "/web3-api-keys/infura/api-key-2",
           ...
           "/web3-api-keys/infura/api-key-17"]
```

### Fluxo de eleicao de API key

```
  +------------------------------+
  | get_keys_sorted_by_consumption|  Consulta Redis db=1
  +------------------------------+  Retorna keys ordenadas por
               |                     numero de requisicoes (menor primeiro)
               v
  +------------------------------+
  | elect_new_api_key            |  Para cada key (menos usada primeiro):
  +------------------------------+    - Tenta SETNX no semaforo (db=0)
               |                       - Se sucesso: key adquirida
               |                       - Se falha: tentar proxima
               v
  +------------------------------+
  | Conexao Web3 estabelecida    |  Web3Handler conecta ao provedor
  | com a key eleita             |  usando URL obtida do SSM
  +------------------------------+
```

**`get_keys_sorted_by_consumption()`**: Consulta o Redis `db=1` para obter os contadores de cada key, ordena por numero de requisicoes em ordem crescente e retorna a lista. Keys que ainda nao existem no contador sao tratadas como tendo zero requisicoes.

**`elect_new_api_key()`**: Itera sobre a lista ordenada e tenta adquirir exclusividade via `SETNX` (Set if Not eXists) no Redis `db=0`. O valor armazenado e o identificador da replica (`socket.gethostname()`). Se uma key esta ocupada por outra replica, a proxima e tentada. Retorna a primeira key adquirida com sucesso.

### Rotacao de API keys

O Job 4 rotaciona a API key em tres situacoes:

1. **A cada 100 transacoes processadas**: A replica libera a key atual (`DELETE` no semaforo), incrementa o contador, e elege uma nova key. Isso distribui a carga uniformemente entre todas as keys disponiveis.

2. **Quando a key e "roubada"**: O metodo `check_if_api_key_is_mine()` verifica periodicamente se o hostname associado a key no semaforo ainda corresponde ao da replica atual. Se outra replica sobrescreveu o semaforo (race condition rara), a replica reelege uma nova key imediatamente.

3. **Limpeza de keys ociosas**: O metodo `free_api_keys()` percorre o semaforo e libera keys cujo registro esta mais antigo que `free_timeout` (padrao: 15 segundos). Isso recupera keys de replicas que falharam sem liberar o semaforo.

```
  loop principal do Job 4:
    |
    +--> processar transacao
    |
    +--> contador_local++
    |
    +--> se contador_local % 10 == 0:
    |      free_api_keys(timeout=15s)   <-- limpa replicas mortas
    |
    +--> se contador_local % 100 == 0:
    |      liberar key atual
    |      eleger nova key
    |      reconectar Web3
    |
    +--> se check_if_api_key_is_mine() == False:
           eleger nova key
           reconectar Web3
```

---

## Logging de Consumo de API Keys

Cada requisicao Web3 e registrada via `KafkaLoggingHandler`, que envia logs estruturados para o topico `mainnet.0.application.logs`. Mensagens de consumo de API seguem o formato:

```
API_request;api_key=/web3-api-keys/infura/api-key-5;method=eth_getTransaction
```

Esses logs sao consumidos pelo Spark Streaming Job descrito abaixo para agregacao.

### Schema do log AVRO

```json
{
  "timestamp": "2024-02-22T15:30:00.123456",
  "logger": "4_mined_txs_crawler",
  "level": "INFO",
  "filename": "4_mined_txs_crawler.py",
  "function_name": "run",
  "message": "API_request;api_key=/web3-api-keys/infura/api-key-5;method=eth_getTransaction"
}
```

---

## Monitoramento via Spark Structured Streaming

O job Spark `1_api_key_monitor.py` (executado em `docker/spark-stream-txs/`) agrega os logs de consumo de API em janelas temporais de 1 dia.

### Pipeline de processamento

```
  mainnet.0.application.logs
           |
           v
  [Spark: leitura do topico Kafka]
           |
           v
  [Remocao do header Confluent (5 bytes)]
           |
           v
  [Desserializacao AVRO]
           |
           v
  [Filtro: message.startswith("API_request")]
           |
           v
  [Extracao: api_key do campo message]
           |
           v
  [Janela temporal: 1 dia, watermark 1 dia]
           |
           v
  [Agregacao: count(*) e max(timestamp) por api_key]
           |
           v
  [Escrita no Redis db=1]
```

### Dados escritos no Redis

Para cada API key, o job escreve um hash no Redis `db=1`:

```
Key:    /web3-api-keys/infura/api-key-5
Fields:
  start       -> "2024-02-22T00:00:00"    (inicio da janela)
  end         -> "2024-02-23T00:00:00"    (fim da janela)
  num_req_1d  -> "4523"                   (total de requisicoes no dia)
  last_req    -> "2024-02-22T23:59:45"    (ultima requisicao registrada)
```

Esses dados sao a base para a logica de `get_keys_sorted_by_consumption()`, que prioriza keys com menor numero de requisicoes.

---

## Script de Monitoramento: Semaphore Collect

O script `n_semaphore_collect.py` executa periodicamente (configuravel via variavel de ambiente) e coleta o estado atual dos semaforos e contadores do Redis:

- **Redis db=0**: Estado de cada key no semaforo (hostname que detem, timestamp)
- **Redis db=1**: Contadores acumulados de consumo
- **Redis db=3**: Grava snapshot consolidado para visualizacao

Isso permite observar em tempo real quais replicas detem quais API keys e qual o consumo acumulado de cada uma.

---

## Teste de API Keys (Batch Job)

O script `dm_test_api_keys.py` (executado como batch job isolado) percorre todos os prefixos SSM conhecidos e testa a validade de cada key:

```python
SSM_PATHS = {
    "/web3-api-keys/alchemy/": "alchemy",
    "/web3-api-keys/infura/":  "infura",
    "/etherscan-api-keys/":    "etherscan",
}
```

Para cada key encontrada, o script tenta uma requisicao de teste ao provedor correspondente e reporta o resultado (sucesso ou falha). Esse job pode ser executado manualmente para validar a configuracao apos alteracoes no SSM.