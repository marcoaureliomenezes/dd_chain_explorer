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

## Semaforo Distribuido com DynamoDB

O Job 4 (Raw Transactions Crawler) opera com multiplas replicas simultaneas (6 em DEV, 8 em PROD), cada uma necessitando de uma API key exclusiva. Para evitar que duas replicas utilizem a mesma key simultaneamente, o modulo `api_keys_manager.py` implementa um mecanismo de semaforo distribuido sobre o DynamoDB.

### Entidades DynamoDB utilizadas

| Entidade (PK) | SK | Finalidade |
|----------|----|-----------|
| `SEMAPHORE` | `{api_key_name}` | Rastreia qual replica detem qual API key (TTL 60s) |
| `COUNTER` | `{api_key_name}` | Acumula o numero total de requisicoes feitas com cada key |

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
  | get_keys_sorted_by_consumption|  Consulta DynamoDB (COUNTER)
  +------------------------------+  Retorna keys ordenadas por
               |                     numero de requisicoes (menor primeiro)
               v
  +------------------------------+
  | elect_new_api_key            |  Para cada key (menos usada primeiro):
  +------------------------------+    - Tenta conditional_put no semaforo
               |                       - Se sucesso: key adquirida
               |                       - Se falha: tentar proxima
               v
  +------------------------------+
  | Conexao Web3 estabelecida    |  Web3Handler conecta ao provedor
  | com a key eleita             |  usando URL obtida do SSM
  +------------------------------+
```

**`get_keys_sorted_by_consumption()`**: Consulta o DynamoDB (entidade `COUNTER`) para obter os contadores de cada key, ordena por numero de requisicoes em ordem crescente e retorna a lista. Keys que ainda nao existem no contador sao tratadas como tendo zero requisicoes.

**`elect_new_api_key()`**: Itera sobre a lista ordenada e tenta adquirir exclusividade via `conditional_put_item()` no DynamoDB (entidade `SEMAPHORE` com TTL de 60s). O valor armazenado e o identificador da replica (`socket.gethostname()`). Se uma key esta ocupada por outra replica, a proxima e tentada. Retorna a primeira key adquirida com sucesso.

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

Esses logs sao consumidos pelo pipeline DLT (Gold views `g_api_keys.etherscan_consumption` e `g_api_keys.web3_keys_consumption`) para agregacao de metricas. Um job periodico no Databricks exporta essas metricas para S3, e uma Lambda `gold_to_dynamodb` sincroniza com o DynamoDB (entidade `CONSUMPTION`).

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

## Monitoramento de Consumo de API Keys

O monitoramento de consumo de API keys e realizado por meio de Gold DLT views no Databricks, que agregam os logs de consumo em janelas temporais.

As views `g_api_keys.etherscan_consumption` e `g_api_keys.web3_keys_consumption` calculam metricas (requests por janela de 1h, 2h, 12h, 24h, 48h) a partir dos logs Silver. Um job periodico (`4_export_gold_to_s3.py`) exporta essas metricas como JSON para S3, onde uma Lambda funcao (`gold_to_dynamodb`) as sincroniza com o DynamoDB sob a entidade `CONSUMPTION`.

Isso substitui o antigo pipeline Spark Streaming + Redis.

> **Nota**: O antigo script `n_semaphore_collect.py` foi eliminado. O estado do semaforo pode ser consultado diretamente no DynamoDB (PK=`SEMAPHORE`) via console AWS ou queries programaticas.

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