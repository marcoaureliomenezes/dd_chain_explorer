# dd_chain_explorer System

Blockchains públicas são redes P2P onde circula uma grande quantidade de capital, na forma de usuários trocando tokens entre si ou interagindo com contratos inteligentes. Por serem redes públicas os dados de transações dentro dessas redes também são de certa forma públicos e podem ser explorados. O sistema aqui implementado é uma plataforma de dados com o intuito de capturar, processar, armazenar e disponibilizar dados de redes blockchain públicas com suporte a contratos inteligentes e do tipo EVM.

## Sumário

- [1. Introdução](#1-introdução)
  - [1.1. Introdução sobre blockchain](#11-introdução-sobre-blockchain)
  - [1.2. Oportunidades em Redes Blockchain](#12-oportunidades-em-redes-blockchain)
  - [1.3. Estudo de caso com 2 contratos inteligentes](#13-estudo-de-caso-com-2-contratos-inteligentes)
  - [1.4. Nota sobre a introdução acima e esse trabalho](#14-nota-sobre-a-introdução-acima-e-esse-trabalho)
- [2. Objetivos deste trabalho](#2-objetivos-deste-trabalho)
  - [2.1. Objetivos de negócio](#21-objetivos-de-negócio)
  - [2.2. Objetivos técnicos](#22-objetivos-técnicos)
  - [2.3. Observação sobre o tema escolhido](#23-observação-sobre-o-tema-escolhido)
- [3. Explicação sobre o case desenvolvido](#3-explicação-sobre-o-case-desenvolvido)
  - [3.1. Provedores de Node-as-a-Service](#31-provedores-de-node-as-a-service)
  - [3.2. Restrições de API keys](#32-restrições-de-api-keys)
  - [3.3. Captura de dados de blocos e transações](#33-captura-de-dados-de-blocos-e-transações)
  - [3.4. Mecanismo para Captura de Dados](#34-mecanismo-para-captura-de-dados)
  - [3.5. Mecanismo de compartilhamento de API Keys](#35-mecanismo-de-compartilhamento-de-api-keys)
- [4. Arquitetura do case](45-arquitetura-do-case)
- [4.1. Arquitetura de solução](#41-arquitetura-de-solução)
- [4.2. Arquitetura técnica](#42-arquitetura-técnica)
- [5. Aspectos técnicos desse trabalho](#5-aspectos-técnicos-desse-trabalho)
  - [5.1. Dockerização dos serviços](#51-dockerização-dos-serviços)
  - [5.2. Orquestração de serviços em containers](#52-orquestração-de-serviços-em-containers)
- [6. Reprodução do sistema dm_v3_chain_explorer](#6-reprodução-do-sistema-dm_v3_chain_explorer)
  - [6.1. Requisitos](#61-requisitos)
  - [6.2. Setup do ambiente local](#62-setup-do-ambiente-local)
  - [6.3. Reprodução do sistema usando o Docker Compose](#63-reprodução-do-sistema-usando-o-docker-compose)
  - [6.4 Visualização do processo de captura e ingestão de dados](#64-visualização-do-processo-de-captura-e-ingestão-de-dados)
- [7. Conclusão](#7-conclusão)
- [8. Melhorias futuras](#8-melhorias-futuras)
  - [8.1. Aplicações downstream para consumo dos dados](#81-aplicações-downstream-para-consumo-dos-dados)
  - [8.2. Melhoria em aplicações do repositório onchain-watchers](#82-melhoria-em-aplicações-do-repositório-onchain-watchers)
  - [8.3. Troca do uso de provedores Blockchain Node-as-a-Service](#83-troca-do-uso-de-provedores-blockchain-node-as-a-service)
  - [8.4. Evolução dos serviços de um ambiente local para ambiente produtivo](#84-evolução-dos-serviços-de-um-ambiente-local-para-ambiente-produtivo)

## 2. Objetivo desse trabalho

**Principal objetivo**: Concepção e implementação de plataforma de dados, entitulada `dd_chain_explorer`, com propósito de capturar, ingestar, processar, armazenar e disponibilizar dados de redes blockchain públicas.

### Escopo do trabalho

- Captura de dados restrito a redes blockchain públicas do tipo EVM;
- Uso da rede Ethereum como rede piloto, devido às características mencionadas na introdução (baixo TPS e alto valor de capital alocado);
- Uso de provedores de Node-as-a-Service para captura de dados;
- Ingestão dos dados em ambiente analitico do tipo Lakehouse;
- Aplicação de arquitetura Medalhão para ingestão e enriquecimento dos dados em ambiente analítico.

### Objetivos específicos

- Criar um sistema de captura de dados deve ser agnóstico à rede de blockchain, desde que usem a EVM como máquina virtual;
- Minimizar latência e números de requisições, e maximizar a disponibilidade do sistema;
- Criar uma plataforma preparada para escalar a captura de dados em redes mais rápidas e escaláveis;
- Criar mecanismos para gerenciamento do consumo de API Keys dos provedores NaaS entre os Jobs que as usam;
- Criar mecanismos para observabilidade do sistema como um todo.

## 3. Explicação sobre o case desenvolvido

Conforme visto na introdução, para se obter dados de uma rede blockchain diretamente, é necessário possuir acesso a um nó pertencente a tal rede.

Com isso, 2 possibilidades se apresentam: **(1)** possuir um nó próprio e **(2)** usar um nó de terceiros.

Devido aos requisitos de hardware, software e rede necessários para deploy de um nó, seja on-premises ou em cloud, foi escolhido nesse trabalho o uso de **provedores de Node-as-a-Service ou NaaS**.

## 3.1. Provedores de Node-as-a-Service

Provedores de NaaS são empresas que fornecem acesso a nós de redes blockchain públicas. Alguns exemplos são **Infura** e **Alchemy**. Como modelo de negócio, fornecem API keys para interação com os nós.

<img src="./img/intro/4_bnaas_vendor_plans.png" alt="4_bnaas_vendor_plans.png" width="100%"/>

Porém, esses provedores restringem a quantidade de requests, de acordo com planos estabelacidos (gratuito, premium, etc.) que variam o preço e o limite de requisições diárias ou por segundo permitidas.

Foi optado pelo **uso de provedores NaaS**. Contudo, devido às limitações de requisições, é preciso um mecanismo para captura de todas as transações em tempo real usando tais provedores. Por se tratar um desafio técnico, reduzir o custo para captura desses dados a zero virtualmente, satisfazendo os objetivos mencionados se mostra um caminho interessante.

### 3.1.1. Restrições de API keys

As requisições em nós disponibilizados por um provedores NaaS são controladas por meio de API Keys. Para o provedor infura as restrições para 1 API Key gratuita são:

- Máximo de **10 requests por segundo**;
- Máximo de  **100.000 requests por dia**.

Na rede Ethereum, um bloco tem tamanho em bytes limitado e é minerado em média a cada 8 segundos. Cada bloco contém em média 200 transações. Isso resulta em:

- **2,7 milhões de transações por dia**;
- **31 transações por segundo**.

As limitações acima impõem um desafio. Como será visto a diante, o mecanismo **para se capturar n transações de um bloco recém-minerado** exige que sejam feitas em média **n requisições** sejam feitas. Usando o plano gratuito, claramente é necessário o uso de várias API Keys.

Porém o gerenciamento de uso dessas API Keys, buscando aumentar a disponibilidade e confiabilidade do sistema traz a necessidade de um mecanismo projetado para tal.

## 3.2. Captura de dados de blocos e transações

Para capturar dados de blocos e transações da rede em tempo real é usada a [Biblioteca Web3.py](https://web3py.readthedocs.io/en/stable/). Ela fornece uma interface para interação com nós de redes blockchain compatíveis com EVM. Entre as várias funções disponíveis, 2 são de interesse para esse trabalho:

**get_block(block_number|'latest')**: 
- Recebe como parâmetro o número do bloco ou a string 'latest' para o bloco mais recente minerado.
- Retorna um dicionário com os **dados e metadados do bloco** e uma **lista de hash_ids** de transações pertencentes ao último bloco minerado.

```python
block_data = web3.eth.get_block('latest')
```

<img src="./img/intro/5_get_latest_block.png" alt="Get latest Block mined" width="80%"/>

Assim é possível identificar novos blocos minerados, ao se perceber que o número do bloco foi incrementado. E então disparar um evento com os dados do bloco.

**get_transaction(tx_hash)**: Retorna um dicionário com os dados da transação referente ao `tx_hash_id` passado como parâmetro.

```python
tx_data = web3.eth.get_transaction('tx_hash_id')
```

<img src="./img/intro/5_get_latest_block.png" alt="Get latest Block mined" width="80%"/>

As 2 funções mencionadas trabalhando em conjunto são suficientes para obter dados de transações recém mineradas. Porém, é necessário que as rotinas que se utilizem delas trabalhem de forma integrada.

Cada chamada nas funções acima consome 1 requisição de uma API Key. Logo, um mecanismo que otimize o uso dessas chaves, minimizando o número de requisições e maximizando a disponibilidade do sistema é necessário.

## 3.4. Mecanismo para Captura de Dados

Conforme mencionado, as 2 funções são suficientes para capturar dados em tempo real de uma rede EVM. Porém, eles precisam atuar em conjunto.

1. O método **get_block('latest')** fornece uma lista de tx_hash_id para transações pertencentes àquele bloco.
2. O método **get_transaction(tx_hash_id)** usa os **tx_hash_id** obtidos do 1º método para capturar os dados de cada transação.

Para que essa cooperação mutua ocorra, são necessários alguns componentes para o sistema.

### 3.4.1. Sistema Pub / Sub

Para a captura dos dados em tempo real, é necessário que 2 jobs cooperem entre si de forma assíncrona. Para alcançar tal finalidade, a inclusão de um componente do tipo  **fila** ou **mensageria do tipo Publisher-Subscriber** se faz necessária.

Uma fila, como por exemplo o **RabbitMQ**, poderia satisfazer os requisitos de comunicação entre os Jobs de forma assíncrona.

- O 1º job captura a lista de **tx_hash_id** e publica em uma fila.
- O 2º job que pode ter réplicas consome essa fila e executa o método **get_transaction(tx_hash_id)** para obter os dados da transação.

Porém, caso se deseje utilizar uma plataforma mais robusta, o uso de um sistema de mensageria do tipo Pub/Sub como o **Apache Kafka** é mais adequado. Ele oferece:

- Comunicação inter processos através de tópicos;
- Sistema robusto e escalável de forma horizontal;
- Capacidade de processar e armazenar grandes volumes de dados, atuando como um **backbone de dados**.

<img src="./img/intro/7_kafka_backbone.png" alt="Kafka Backbone" width="80%"/>

O sistema **dm_v3_chain_explorer** deve estar preparado para capturar e ingestar dados de redes blockchain do tipo EVM, não estando restrito a Ethereum.

A Ethereum é a rede mais lenta e menos escalável entre as redes EVM. Por isso, o sistema deve estar preparado para capturar dados de redes mais rápidas , o que se traduz em volumes maiores, alta throughput de dados que esse componente deve suportar. Logo, a plataforma de mensageria escolhida deve ser capaz de suportar workloads de bigdata.

Portanto, pelos requisitos apresentados de escalabilidade, resiliência e robustez. O **Apache Kafka** se mostrou o componente ideal para a finalidade apresentada.

### 3.4.2. Captura dos dados do bloco recém minerados (Mined Blocks Crawler)

O job **mined_blocks_crawler** que encapsula a chamada da função **get_block('latest')**, já mencionada. Ele opera da seguinte forma:

- A cada período de tempo, por padrão 1 segundo, ele executa a função `get_block('latest')`, capturando os dados do bloco mais recente.
- Observando o campo **blockNumber** dos dados retornados, ele identifica se houve um novo bloco minerado (block number incrementado).
- A identificação de um novo bloco minerado dispara um evento, que resulta em 2 ações:
  - Os metadados do bloco são publicados em um tópico chamado **mined.blocks.metadata**.
  - A lista de `tx_hash_id` contendo ids de transações do bloco são publicados em um tópico chamado **mined.txs.hash.ids**.

**Observação:** a cada execução do método **get_block('latest')** uma requisição é feita usando a API key. Com a **frequência 1 req/segundo**, tem-se **86.400 requisições por dia**. Portanto, para satisfazer tal número de requisições 1 chave é o suficiente.

### 3.4.3. Captura de dados de transações (Mined Transactions Crawler)

O job **mined_txs_crawler** encapsula a chamada da função **get_transaction(tx_hash_id)**. Ele opera da seguinte forma:

- Inicialmente ele se subscreve no tópico **mined.txs.hash.ids** de forma a consumir os `hash_ids` produzidos pelo job **mined_blocks_crawler**.
- A cada `hash_id` consumido, ele executa o método `get_transaction(tx_hash_id)` para obter os dados da transação.
- Com os dados da transação ele classifica essa transação em 1 dos 3 tipos:
  - **Tipo 1**: Transação de troca de token nativo entre 2 endereços de usuários (Campo `input` vazio) ;
  - **Tipo 2**: Transação realizando o deploy de um contrato inteligente (Campo `to` vazio) ;
  - **Tipo 3**: Interação de um endereço de usuário com um contrato inteligente (Campo `to` e `input` preenchidos).

Cada tipo de transação é publicado em um tópico específico:

- **mined.txs.token.transfer**: transação de troca de token nativo entre 2 endereços de usuários;
- **mined.txs.contract.deploy**: transação realizando o deploy de um contrato inteligente;
- **mined.txs.contract.call**: Interação de um endereço de usuário com um contrato inteligente.

Após classificados em tópicos, cada tipo de transação pode alimentar aplicações downstream, cada uma com sua especificidade.

#### Observação sobre a carga de trabalho nesse job

O job **mined_txs_crawler** é responsável pelo maior volume de requisições. Se o job **mined_blocks_crawler** precisa 1 requisição por intervalo de tempo, setado em 1 segundo e totalizando 86.400 requisições por dia, o job **mined_txs_crawler** precisa de 1 requisição por transação minerada. Como visto, a rede Ethereum tem uma média de 31 transações por segundo. Isso resulta em 2,7 milhões de transações por dia.

Então para que os objetivos de latência e disponibilidade do sistema sejam atendidos, é necessário que o job **mined_txs_crawler** tenha um mecanismo de controle de uso de API Keys. Esse mecanismo está detalhado na seção 3.5.

### 3.4.4.  Decode do campo input em transações (Tx Input Decoder)

As transações publicadas no tópico **mined.txs.contract.call** correspondem a interação com contratos inteligentes. Essa interação se dá por meio dos campos **to** e **input**, contidos na transação. O campo `to` contém o endereço do contrato inteligente e o campo `input` contém a chamada de função e os parâmetros passados para ela. Por exemplo, para se trocar Ethereum por outros tokens na rede Uniswap, é necessário chamar a função `swapExactETHForTokens` passando os parâmetros necessários.

Porém, a informação no campo `input` está encodada. É necessário um mecanismo para decodificar esses dados. Para essa finalidade foi criado o job **txs_input_decoder**.

Para que isso seja possível, é necessário o uso da **ABI (Application Binary Interface)** do contrato inteligente. Uma ABI é uma estrutura de dados que contém a assinatura de todas as funções do contrato. Com a ABI de um contrato é possível decodificar o campo `input` e extrair as informações valiosas ali contidas. As aplicações descritas na introdução, como arbitragem e liquidação, ou mesmo a identificação de ações de hackers dependem da decodificação desses dados.

Com as informações decodificadas, o job **txs_input_decoder** publica as informações em um tópico chamado **mined.txs.input.decoded**.

## 3.5. Mecanismo de compartilhamento de API Keys

Nesse job concentra-se o esforço em número de requisições.Como mencionado, o número de transações diárias na rede Ethereum ultrapassam em muito os limites de uma API Key para 1 plano gratuito. Logo é necessário que esse job seja escalado. Mas escalado de que forma?

Para segurança do sistema, essas API Keys não podem estar cravas no código, pois a mesma rotina será usada por diferentes instâncias do job. A 1ª solução que vem a mente é passar a API Key por parâmetro. Porém, isso não é seguro. Caso uma API Key tenha seus recursos esgotados, o job não poderá mais consumir dados e não haverá uma maneira de se manter o controle sobre isso. Para garantir os requisitos de **latência e disponibilidade do sistema**, é preciso um mecanismo mais sofisticado para que esses jobs compartilhem as API Keys de forma inteligente.

**Redução da Latência**: Cada API Key é limitada por requests por segundo. Então, se há multipals instâncias do job **raw_tx_ingestor** consumindo dados, é preciso que em dado instante de tempo t, cada API Key seja usada por somente 1 job. Dessa forma, a taxa de requisições por segundo é maximizada.

**Máxima disponibilidade**: Para garantir a disponibilidade do sistema, é preciso manter o controle de requisições nas API Keys para que somente em último caso as requisições sejam esgotadas.
Caso o número de requisições diárias seja atingido o job deve trocar de API Key. É interessante também que as instâncias do job troquem de API Keys de tempos em tempos, para que todas as API Keys sejam usadas de maneira equitativa. Para isso, é preciso um mecanismo de controle de uso das API Keys.

Para que o Job  **raw_tx_ingestor** em suas **n réplicas** consumam **m API Keys**, buscando atender aos 2 requisitos acima, se faz necessário que:

- Para **`n` réplicas de jobs raw_tx_ingestor** são necessárias **`m` chaves**, sendo **`m` > `n`**.
- Para cada **instante de tempo `T`**, uma **api key `i`** deve ser utilizada por apenas **1 job replica `j`**.

Como pode ser visualizado na seção de arquitetura de solução, o job **raw_tx_ingestor** usa o mecanismo para atender aos requisitos listados. Esse mecanismo está aqui dividido em leitura e escrita.

#### Leitura

1. Ao ser instanciado o job **raw_tx_ingestor** recebe um conjunto de API Keys que ele pode utilizar. Essas API Keys estão na forma de pseudo-nomes. Por exemplo, `api_key_1`, `api_key_2`, `api_key_3`, etc. Esses pseudo-nomes são chaves para segredos armazenados no recurso **Azure Key Vault**, de forma a garantir a segurança das API Keys.

2. O job consulta um banco de dados do tipo chave-valor, neste caso o **Redis**, para ver se dop conjunto de API Keys recebidas qual delas não está sendo usada.

3. Ao identificar quais API Keys estão livres, o job **raw_tx_ingestor** consulta um banco de dados que armazena o número de requisições daquelas API Keys nas últimas 24 horas e escolhe a API Key que tem menos requisições.

#### Escrita

1. Ao iniciar o uso de uma API Key a replicado job **raw_tx_ingestor** marca tal chave como ocupada no bando de dados chave-valor **Redis**.

2. Ao realizar uma requisição com determinada API Key, o job **raw_tx_ingestor** publica uma mensagem em um tópico do Kafka destinado a logs.

Existe então o 3º job, do tipo Spark Streaming chamado **api_key_monitor**  que tem como tarefa consumir as mensagens do tópico de logs. Usando filtros e windowing, ele calcula o número de requisições nas últimas 24 horas para cada API Key e então atualiza uma tabela no banco de dados Scylla.

É justamente essa tabela que o Job **raw_tx_ingestor** consulta para escolher a API Key a ser usada em questão de menos requisições diárias.

## 4. Arquitetura do case

Nessa seção está detalhada a arquitetura do sistema **dm_v3_chain_explorer**.O objetivo aqui é compreender como esses componentes do sistema se comunicam entre si e com serviços auxiliares, bem como os mesmos são deployados, orquestrados e monitorados.

- **Arquitetura de solução**: Descrição de alto nível de como o sistema funciona para captura e ingestão de dados no Kafka, processamento e persistência dos dados em uma camada analítica.

- **Arquitetura técnica**: Descrição detalhada de como os componentes do sistema se comunicam entre si e com serviços auxiliares, bem como os mesmos são deployados,orquestrados e monitorados.

## 4.1. Arquitetura de solução

Podemos dividir a arquitetura de solução em 2 partes:

- **Captura e ingestão de dados em tempo real**: Essa parte é responsável por capturar os dados brutos da rede Ethereum, classificar e decodificar esses dados e persistir no Apache Kafka. Com os dados no kafka, estes serão consumidos por conectores do Kafka Connect para o Hadoop.

- **Processamento e persistência dos dados**: Essa parte é responsável por processar os dados brutos capturados e persistidos HDFS e processa-los em uma arquitetura de medalhão.

O desenho abaixo ilustra como a solução para captura e ingestão de dados da Ethereum no Kafka funciona.

![Arquitetura de Solução Captura e Ingestão Kafka](./img/arquitetura/1_arquitetura_ingestão_fast.png)

Os componentes dessa solução são:

- **Apache Kafka**: Plataforma de streaming distribuída que permite publicar e consumir mensagens em tópicos. É altamente escalável e tolerante a falhas. É o backbone do sistema Pub-Sub.
- **Redis**: Banco de dados chave-valor em memória usado para armazenar dados sobre uso de API KEYs.
- **Scylla**: Banco de dados NoSQL altamente escalável e tolerante a falhas usado para armazenar dados sobre uso de API KEYs.
- **Azure Key Vault**: Serviço de segredos da Azure usado para armazenar as API Keys.
- **Apache Spark**: Framework de processamento de dados em tempo real usado para monitorar o uso das API Keys.
- **Jobs implementados em python Python**: Esses jobs são responsáveis por capturar, classificar e decodificar os dados usando as ferramentas mencionadas acima. Executam em containers docker.
- **Kafka Connect**: Ferramenta usada para conectar o Kafka a diferentes fontes de dados. Nesse caso, o Kafka Connect é usado para envio dos dados de tópicos do Kafka para outros sistemas.
