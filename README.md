# dm_v3_chain_explorer System

Neste repositório estão implementadas e documentadas rotinas de extração, ingestão, processamento, armazenamento e uso de dados com origem em protocolos P2P do tipo blockchain, assim como definições imagens docker e arquivos yml com serviços utilizados. Esse trabalho foi desenvolvido para o case do programa Data Master.

## Sumário

1. [Objetivo do Case](#1---objetivo-do-case)
2. [Arquitetura](#2---arquitetura)
3. [Explicação sobre o case desenvolvido](#3---explicação-sobre-o-case-desenvolvido)
4. [Aspectos técnicos desse trabalho](#4---aspectos-técnicos)
5. [Melhorias e considerações finais](#5---melhorias-e-considerações-finais)
6. [Reprodução da arquitetura](#6---reprodução-da-arquitetura)
7. [Appendice](#7---appendice)

## 1 - Objetivo do Case

O objetivo final desse trabalho é sua submissão para o programa Data Master, e posterior apresentação do mesmo à banca de Data Experts. Nessa apresentação serão avaliados conceitos e técnicas de engenharia de dados, entre outros campos, aplicados na construção prática deste sistema entitulado **dm_v3_chain_explorer**.

Para alcançar tal objetivo final e, dados os requisitos do case, especificados pela organização do programa, para a construção desse sistema foram definidos objetivos específicos, categorizados em objetivos de negócio e objetivos técnicos.

### 1.1 - Objetivos de negócio

A solução apresentada aqui tem como objetivo de negócio prover um sistema capaz de capturar, ingestar e armazenar dados com origem em **redes P2P do tipo blockchain**. Quando se fala em blockchain 2 conceitos podem confundir.
O termo blockchain pode ser usado pra se referir a:

- Estrutura de dados blockchain que armazena blocos. Cada bloco contém transações efetuadas por usuários da rede entre outros metadados. Um desses metadados é o hash do bloco anterior, o que garante a integridade da cadeia de blocos.

- Rede de blockchain, de topologia Peer-to-Peer onde nós validam transações e mineram novos blocos, estes construídos em uma estrutura de dados blockchain. Todos os nós da rede possuem uma cópia dessa estrutura de dados e são sincronizados entre si. Assim, novos blocos minerados, após consenso, são adicionados ao blockchain e sincronizados entre o restante dos nós para que a rede possa validar a integridade das transações contidas em todos os blocos.

#### 1.1.1 - Redes Blockchain Públicas

- Blockchains públicas são redes P2P que armazenam uma estrutura de dados do tipo blockchain. Por serem públicas permitem que qualquer nó possa ingressar na rede. Obviamente, desde que (1) os requisitos necessários para acessar um nó da rede P2P em questão e (2) os meios de interagir com esse nó e processar os dados obtidos a partir dele sejam satisfeitos.

#### 1.1.2 - Oportunidades em blockchains públicas

Atualmente existem inúmeras redes blockchain onde circula uma quantidade significativa de capital. Essas redes são usadas para, desde a transferência de tokens entre endereços, até a execução funções em contratos inteligentes. Entre as principais redes de blockchain públicas estão:

1. Bitcoin;
2. Ethereum;
3. Binance Smart Chain;
4. Solana;
5. Polygon.

Vamos explorar aqui 2 possibilidades.

1. Em [Defi Llama Top Blockchains List](https://defillama.com/chains) ver o quanto de está alocado em cada uma dessas redes. A rede Ethereum, por exemplo, é a rede com maior capital preso no protocolo (TVL). Por se só ja é interessante ingestar em tempo real os dados de transações de uma rede como essa. É inegável que as instituções financeiras olham com interesse para oferecer como produto a venda desses tokens, tais como BTC e ETH. Mas qual seria o 1º passo para que uma instituição financeira, altamente regulada, possa oferecer um produto como esse? E prover mecanismos de segurança, para, por exemplo, monitorar e assegurar quem sansões de lavagem de dinheiro e financiamento ao terrorismo não estão sendo infringidas?

2. Nessas redes, além de transações de transferência de tokens, são executadas funções em contratos inteligentes. Esses contratos são programas deployados em um bloco da rede com endereço próprio. Após deployados esses contratos passam a estar disponíveis para interação. Isso permite que aplicações descentralizadas (dApps) sejam criadas dentro do protocolo. Dessa forma, é possível criar aplicações financeiras descentralizadas (DeFi) que permitem empréstimos, trocas de tokens, entre outras funcionalidades. Em [Defi Llama Top DeFi protocols](https://defillama.com/) é possível ver uma lista de aplicações DeFi e o volume de capital aplicado em cada uma delas. Ao capturar as transações em tempo real, transações do tipo interação com contratos inteligentes, que possuem um campo de dados chamado `input`, é possível monitorar qual usuário está chamando qual função do contrato e com qual argumento. Não cabe aqui mensurar a vasta gama de oportunidades que se abrem ao capturar esses dados e processá-los.

### 1.2 - Objetivos técnicos

Para alcançar os objetivos de negócio propostos é preciso implementar um sistema capaz de capturar, ingestar, processar, persistir e utilizar dados da origem mencionada. Para isso, foram definidos os seguintes objetivos técnicos:

- Criar sistema de captura de dados brutos de redes de blockchain públicas.
- Criar um sistema de captura de dados de estado de contratos inteligentes.
- Criar um sistema de captura agnóstico à rede de blockchain, prém restrito a redes do tipo EVM (Ethereum Virtual Machine).
- Criar uma arquitetura de solução que permita a ingestão lambda.
- Minimizar latência e números de requisições, e maximizar a disponibilidade do sistema.
- Criar um ambiente reproduzível e escalável com serviços necessários à execução de papeis necessários ao sistema.
- Armazenar e consumir dados pertinentes a operação e análises em bancos analíticos e transacionais.
- Implementar ferramentas monitorar o sistema (dados de infraestrutura, logs, etc).

### 1.3 - Observação sobre o tema escolhido

Dado que a tecnologia blockchain não é assunto trivial e também não é um requisito especificado no case, no corpo principal desse trabalho evitou-se detalhar o funcionamento de contratos inteligentes e aplicações DeFi. Porém, é entendido pelo autor desse trabalho que, apesar de não ser um requisito especificado no case, inúmeros conceitos aqui abordados exploram com profundidade campos como:

- Estruturas de dados complexas (o próprio blockchain);
- Arquiteturas de sistemas distribuídos e descentralizados;
- Conceitos ralacionados a finanças.

Portanto, a escolha desse tema para case é uma oportunidade de aprendizado e de aplicação de conhecimentos de engenharia de dados, arquitetura de sistemas, segurança da informação, entre outros. Caso o leitor deseje se aprofundar mais nesse tema, a **seção Appendice** desse documento é um ótimo ponto de partida.

## 2 - Arquitetura

Nesse tópico está detalhada a arquitetura de solução e técnica do **dm_v3_chain_explorer**.

### 2.1 - Arquitetura de solução

Para detalhar a arquitetura de solução desse trabalho, é preciso extrair dos objetivos técnicos decisões tomadas e requisitos para o sistema.

#### 2.1.1 - Decisões tomadas

1. Foi escolhido fazer ingestão de dados da rede Ethereum. Isso se justifica pelo fato de que a rede Ethereum é a rede com maior capital preso em tokens, sendo a melhor escolha para um requisito de negócio. Além disso, a rede Ethereum é uma rede do tipo EVM. Portanto, a solução proposta é agnóstica à rede de blockchain, mas restrita a redes do tipo EVM.

2. Para capturar dados da rede é preciso ter um nó na rede Ethereum. Devido aos requisitos de hardware e software necessários para deploy de um nó on-premises ou em cloud, foi escolhido o uso de provedores de `Node-as-a-Service`. Esses provedores fornecem uma API para interação com um nó da rede Ethereum limitando o número de requisições por segundo e por dia usando uma API KEY.

#### 2.1.2 - Requisitos para o sistema

O requisito inicial do sistema é capturar e ingestar os dados brutos de transações da rede Ethereum com a menor latência possível. Dado que foi optado pelo uso de provedores de `Node-as-a-Service`, é preciso considerar os seguintes fatores:

- As requisições em nós disponibilizados por um provedor de `Node-as-a-Service` são limitadas. O provedor infura por exemplo, sua API KEY em plano gratuito oferece 10 requisições por segundo e 100.000 requisições por dia.

- Na rede Ethereum, um bloco é minerado a cada 8 segundos e contém cerca de 250 transações. Isso resulta em uma quantidade diária de mais de 2 milhões de transações. Portanto, para capturar esses dados, é necessário minimizar o número de requisições e manter um controle de uso das API KEYs.

Dados os pontos o desenho de solução para ingestão de dadoss da Ethereum em tempo real está ilustrado a seguir.

![Arquitetura de Solução Captura e Ingestão Kafka](./img/arquitetura_solucao_ingestao_fast.png)

NAs seções seguintes é demonstrado como os diferentes serviços colaboram entre si para capturar os dados e colocá-los em tópicos do Kafka.

### 2.2 - Arquitetura Técnica

- **Camada Fast**: Camada de ingestão de dados em tempo real.
- **Camada Batch**: Camada de processamento de dados em batch.
- **Camada de Aplicação**: Camada com aplicações que interagem com blockchain.
- **Camada de Operação**: Camada com serviços necessários ao monitoramento do sistema.

Foi optado nesse trabalho pela construção de um ambiente híbrido, ou seja, usando recursos de cloud e on-premises mas com foco no on-premises. Nesta versão os serviços de cloud utilizados se restringem ao Key Vault e ao Azure Tables, ambos serviços da Azure e de um Service Principal para autenticação.

Apesar da opção de construir um projeto full cloud se apresentar, a escolha pela construção de algo local usando docker permite que futuramente as mesmas imagens sejam usadas para deploy em ambientes cloud e/ou, possíveis alterações de serviços aqui deployados no Docker, tais como o Kafka ou o próprio HDFS do Hadoop sejam substituídos por análogos de algum provedor Cloud.

Os recursos de infraestrutura on-premises usados aqui se dividem em 2 ambientes da seguinte forma:

- **Ambiente DEV**: 1 computador local com docker instalado e **Docker Compose** como orquestrador de containers.
- **Ambiente PROD**: 1 cluster de computadores na rede local com docker instalado e usando o **Docker Swarm** como orquestrador.

O uso de docker possibilita que imagens possam ser instanciadas em containers, que se assemelham, nas devidas proporções, a computadores isolados, tornando a ferramenta ideal para simular um ambiente distribuído. Os containers encapsulam todo software necessário para execução de um serviço ou aplicação definidos da imagem, o que o torna portável para execução no computador do leitor ou em outros ambientes com a engine do docker instalada. As definições de imagens para esse trabalho se encontram no diretório `docker/`.

Para orquestração de containers, foram utilizadas as ferramentas **Docker Compose** e **Docker Swarm**, para os ambientes de "Desenvolvimento" e "Produção", respectivamente. As definições de serviços para essas ferramentas se encontram no diretório `services/`.

### Camadas do sistema

Os recursos :

- Na **camada Batch** estão definidos serviços relacionados a um Cluster Hadoop, junto a ferramentas que trabalham com tal cluster de forma conjunta, tais como o Apache Spark, Apache Airflow, entre outros.

- Na **camada Fast** estão definidos serviços relacionados a um cluster Kafka e ferramentas de seu ecossistema, tais como Kafka Connect, Zookeeper, Schema Registry, o ScyllaDB, entre outros.

- Na **camada de Operação** estão definidos serviços que monitoram a infraestrutura do sistema, como Prometheus, Grafana e exporters de métricas necessários para monitoramento.

- Na **camada de Aplicação** estão definidas rotinas que interagem com a rede de blockchain para capturar os dados, ingestá-los, processa-los e armazena-los no serviços dos layers Batch e Fast.

Uma visão geral dos diferentes serviços dispostos em layer que compões esse sistema está ilustrada no diagrama a baixo.

![Serviços do sistema](./img/batch_layer.drawio.png)

Esse desenho acima traz um panorama geral. Os serviços das camadas Batch, Fast e Aplicação se encontram definidas em arquivos .yml na pasta `services/` onde:

**Layer Batch**: `services/cluster_dev_batch.yml` para DEV e `services/cluster_prod_batch.yml` para PROD.
**Layer Fast**: `services/cluster_dev_fast.yml` para DEV e `services/cluster_prod_fast.yml` para PROD.
**Layer Aplicação**: `services/cluster_dev_app.yml` para DEV e `services/cluster_prod_app.yml` para PROD.

Já os serviços da camada de Operação estão definidos nos arquivos .yml na pasta `services/operation/`. A seguir, no tópico de **Arquitetura de Solução** é explorado com mais detalhes:

1. Como as aplicações streaming interagem entre si, usando serviços do layer fast.
2. Como pipelines de Jobs em batch são orquestrados e executados interagindo com serviços do layer batch.

### 2.1 - Arquitetura de Solução

A arquitetura de solução desse trabalho é composta por 2 camadas principais, a camada de ingestão e processamento de dados em tempo real e a camada de ingestão e processamento de dados em batch. Devido a características intriscecamente diferentes entre esses dois tipos de processamento, se faz necessário a separação de camadas.

### 2.1.1 - Ingestão e processamento de dados em tempo real

Na camada de ingestão e processamento de dados em tempo real, é preciso considerar alguns fatores que influenciaram a escolha de ferramentas e composição de jobs colaborativos entre si. A seguir estão listados os fatores considerados:

1. Redes de blockchain operam minerando blocos com certa frequência.
2. Um bloco minerado quer dizer o bloco e suas respectivas transações foram validadas e persistidos no ledger.
3. Para capturar dados de blocos minerados é necessário fazer 1 requisição a um nó da rede P2P.
4. Para capturar dados de uma transação é necessário fazer 1 requisição a um nó da rede P2P.
5. Requisições a nós de redes P2P são limitadas por provedores de Node-as-a-Service.

Dados os fatores enumerados acima e também os objetivos desse trabalho, de capturar dados de transações, ingestá-los e processá-los em tempo real minimizando a latência, a necessidade do desenho de solução a seguir se apresenta:

![Arquitetura de streaming-transactions](./img/arquitetura_DM.drawio.png)

Diferentes jobs colaboram entre si para capturar os dados e colocá-los em um tópico do Kafka. Cada um desses Jobs faz uso de uma API Key para efetuar requisições a um provedor de Node-as-a-Service para capturar os dados. 

Na arquitetura de solução acima diferentes API Keys são compartilhadas entre os Jobs de forma a minimizar o número de requisições e maximizar a disponibilidade do sistema. Na seção 3 será examina com mais detalhes a implementação dessa arquitetura, assim como uma demonstração de como a mesma funciona.

### 2.1.2 - Ingestão e processamento de dados em batch

ESCREVER

### 2.2 - Arquitetura Técnica


A arquitetura técnica deste sistema é composta de 2 ambientes, um para desenvolvimento e outro para produção. Essa decisão foi tomada para que fosse possível desenvolver e testar o sistema em um ambiente controlado e depois subir o sistema em um ambiente realmente distribuído.

Para ambos os ambientes a ferramenta básica foi o Docker, que foi utilizada para criar containers que simulam clusters de serviços. A escolha do Docker se deu pelos seguintes motivos:

- **Portabilidade**: Com o docker, é possível criar containers que podem ser executados em qualquer ambiente, independente do sistema operacional ou da infraestrutura.
- **Isolamento**: Cada container é isolado do restante do sistema, o que permite que diferentes serviços sejam executados em um mesmo ambiente sem que haja conflitos.
- **Reprodutibilidade**: Conforme um dos requisitos do case, é necessário que a solução proposta seja reproduzível. Com o docker, é possível criar imagens que podem ser compartilhadas e instanciadas como containers em qualquer ambiente, desde que o docker esteja instalado e requisitos mínimos de hardware sejam atendidos.

Para orquestrar a execução dos containers, foram utilizadas as ferramentas `Docker Compose` e `Docker Swarm`, para os ambientes de "Desenvolvimento" e "Produção", respectivamente.

#### Apache Kafka

#### ScyllaDB

```bash

docker exec -it scylladb cqlsh -e "select * from operations.api_keys_node_providers ;"

```

#### 2.2.1 Ambiente de "Desenvolvimento"

O ambiente de desenvolvimento é composto por um clusters de serviços que executam em um único nó. A escolha de um único nó para o ambiente de desenvolvimento se deu por questões de custo e praticidade. A seguir estão listados os clusters de serviços que compõem o ambiente de desenvolvimento:

#### 2.2.2 - Recursos computacionais usados em cluster de "Desenvolvimento"

| Node          | IP            | Hostname                  | Usuário  | OS Version         | CPUs | Arquitetura | Model                                     | Memória RAM | Memória SWAP |
|---------------|---------------|---------------------------|----------|--------------------|------|-------------|-------------------------------------------|--------------|-------------|
| Node Master   | 192.168.15.101| `dadaia@dadaia-desktop`   | dadaia   | Ubuntu 22.04.4 LTS | 8    | x86_64      | Intel(R) Core(TM) i7-2600 CPU @ 3.40GHz   | 15866,8 MB   | 2048,0 MB   |

#### 2.2.3 Ambiente de "Produção"

O ambiente de produção é composto por 4 clusters de serviços que executam em 4 nós diferentes. Para isso foram utilizados 4 nós de uma rede local, compostos por computadores com recursos listados no tópico a seguir. A decisão de criação deste ambiente se fez pelos seguintes motivos:

- A quantidade de serviços orquestrados para exibir a funcionalidade completa do sistema é grande. E quando junto de uma apresentação compartilhando a tela, a execução de todos os serviços em um único nó pode ser inviável.

- Neste trabalho estão sendo utilizadas ferramentas de Big Data, como Apache Kafka e ScyllaDB, Apache Spark, entre outras. Por esse motivo, agrega valor a construção de um ambiente distribuído, onde seja possível deployar serviços como o Kafka, Spark e o ScyllaDB em clusters e também se deparar com desafios desses ambientes, como por exemplo o workflow de deploy de serviços no cluster.

- A construção de um ambiente distribuído é uma oportunidade de aprendizado e de aplicação de conhecimentos de engenharia de dados, arquitetura de sistemas, segurança da informação, entre outros.

#### 2.2.4 Recursos computacionais usados em cluster de "Produção

Figura Prometheus

## 3 - Explicação sobre o case desenvolvido

### 3.1 - Obtenção de dados da Origem

Nesse case foram utilizados dados de origem em redes de blockchain públicas do tipo EVM. Neste tipo de rede a seguinte variedade de dados pode ser obtida:

- Dados de blocos minerados e suas respectivas transações;
- Dados de variáveis de estado em contratos inteligentes deployados na rede.

### 3.1.1 - Dados de blocos e transações

Em redes Blockchain do tipo EVM, a cada intervalo de tempo, um novo bloco é minerado contendo transações. É possível visualizar esse processo em websites como [Etherscan](https://etherscan.io/) para a rede Ethereum ou [Polyscan](https://polygonscan.com/) para a Polygon. As transações efetuadas podem ser dos seguintes tipos:

- Transações de transferência de tokens entre endereços;
- Transações de com chamadas para execução de contratos inteligentes;
- Transações de deploy de novos contratos inteligentes;

Como pode ser visto com mais profundidade na seção de apendice deste documento, redes de blockchain públicas possuem as seguintes características:

- São denominadas públicas por serem redes P2P que permitem que qualquer pessoa possa se tornar um nó da rede.
- A estrutura dedados blockchain é por natureza distribuída. Todos os nós da rede P2P possuem uma cópia do ledger (estrutura de dados que contém todos os blocos) e são sincronizados entre si, para que possam validar transações e minerar novos blocos.

Então para se ter acesso a dados de uma rede blockchain pública, é necessário que se tenha acesso a um nó da rede. A interação com um nó da rede é feita por meio de APIs oferecidas pela comunidade de desenvolvedores de cada protocolo para diferentes linguagens de programação.

### 3.1.2 - Nós de Blockchain e Provedores Node-as-a-Service

Dada a conclusão acima, é preciso acessar um nó da rede para se ter acesso aos dados. Para isso, existem 2 possibilidades

#### Deploy de um nó na rede

É possível fazer o deploy de um nó em ambiente on-premises ou em cloud. Isso pode ser feito por meio de um provedor de cloud, como AWS, Azure, Google Cloud, entre outros. E então, por meio de APIs, é possível acessar os dados da rede.

- **Vantagem**: Número de requisições não é limitado por um provedor.
- **Desvantagem**: Requisitos de hardware e de software necessários para deploy de um nó on-premises ou em cloud.

#### Utilização de provedores de Node-as-a-Service

Existem no mercado provedores de Node-as-a-Service, que oferecem acesso a nós de redes de blockchain públicas por meio de APIs. Esses provedores oferecem planos de acesso que variam de acordo com o número de requisições e o tipo de requisição. Alguns exemplos de provedores são:

- [Infura](https://infura.io/)
- [Alchemy](https://www.alchemy.com/)

A utilização de provedores de Node-as-a-Service é uma opção interessante para esse case, em período de prototipação.

- **Vantagem**: Número de requisições é limitado por um provedor.
- **Desvantagem**: Requisitos de hardware e de software necessários para deploy de um nó on-premises ou em cloud.

Para esse case, foi utilizada a opção de provedores de Node-as-a-Service. Os provedores escolhidos foram **infura** e **alchemy**, que oferece planos de acesso gratuitos e pagos. A desvantagem citada, sobre o número de requisições ser limitado por um provedor, torna necessária a implementação de mecanismos para minimizar o mesmo.

Porém, esse fator, ao invés de limitar a solução, agrega valor a mesma, visto que a implementação de mecanismos para minimizar o número de requisições é uma oportunidade de aprendizado e de aplicação de estratégias engenhosas para sobrepor tal limitação.

#### Tabela de limites de requisições dos provedores de Node-as-a-Service:

| Provedor | Limite de requisições por segundo | Limite de requisições por dia |
|----------|-----------------------------------|-------------------------------|
| Infura   | 10                                | 100.000                       |
| Alchemy  | 5                                 | 1.000.00                      |

A rede etherem possui uma média de 1 Bloco a cada 8 segundos e 250 transações por bloco, o que resulta em média de 31,25 transações por segundo ou 2.700.000 transações por dia. Portanto, para atender aos objetivos desse trabalho foram necessários os seguintes recursos:

- Mobilização de amigos e familiares para que eles pudessem se cadastrar com o e-mail nos sites dos provedores e cederem as APIs Keys. Foram obtidas nesse processo **22 API Keys**, visto que cada pessoa poderia criar 1 conta em cada provedor.

- Construção de mecanismo para capturar essas transações que minimiza o número de requisições e também que compartilhe o uso das APIs Keys para que não haja problemas de limites de requisições e as aplicações funcionem de forma distribuída compartilhando o uso das APIs Keys.

#### 3.1.3 - Acesso a dados de blockchain por meio de APIs

Como comentado, os dados dentro de um nó se tornam acessiveis através do uso de APIs. Uma delas, oferecidas pela comunidade na linguagem Python, é a [Web3.py](https://web3py.readthedocs.io/en/stable/). Ela é uma biblioteca que permite a interação com nós da rede blockchain do tipo EVM. A seguir está um exemplo de código que utiliza a biblioteca **Web3.py** para acessar dados do último bloco minerado **get_block(latest)** e de uma transação com o método **get_transaction('0xTX_HASH_ID')**.

```python
from web3 import Web3

# Conexão com um nó da rede Ethereum
w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/API_KEY_INFURA'))

# Acessando dados de um bloco
block = w3.eth.get_block('latest')
print(block)

# Acessando dados de uma transação
tx = w3.eth.get_transaction('0xTX_HASH_ID')
print(tx)

```

- **Dados de contratos inteligentes**: Em protocolos EVM, contratos inteligentes são programas de computadores que são deployados em um bloco da rede com endereço próprio. Após deployados esses contratos passam a estar disponíveis para interação. Isso permite que aplicações descentralizadas (dApps) sejam criadas dentro do protocolo.

### 3.1 - Ferramentas utilizadas

#### 3.1.1 Docker



#### Serviços e portas abertas



#### 3.1.2 Orquestração de containers



#### Docker Compose e ambiente local

Devido a quantidade de serviços a serem orquestrados, foi utilizado o `Docker Compose` para orquestração de containers no localhost.

Vantagens desse ambiente de DEV:

- **Facilidade de uso**: Com o `Docker Compose`, é possível orquestrar a execução de vários containers com um único comando.
- **Desenvolvimento Integrado**: É possivel desenvolver as rotinas de ingestão e processamento de dados de maneira integrada aos serviços também deployados (Kafka, Hadoop e outros). Isso se dá concretamente da seguinte forma:
  - Usando volumes monta-se diretórios locais aos diretórios de trabalho dos containers.
  - O container é deployado no docker-compose com o entrypoint de loop infinito, para que o container não finalize sua execução.
  - O container é acessado via `docker exec -it {container_id} bash`.
  - Dentro do container a rotina em desenvolvimento é executada por linha de comando.
  - O resultado é observado em tempo real no diretório local montado como volume.

### 1.2.2 Inicialização do ambiente de Desenvolvimento

No shell script `start_dm_dev_cluster.sh` é possível observar a inicialização do ambiente de desenvolvimento. O script é responsável por:

- Inicializar os containers referentes a serviços da camada fast, definidos em `cluster_dev_fast.yml`.
- Inicializar os containers referentes a serviços da camada de aplicação web, definidos em `cluster_dev_app.yml`.
- Inicializar os containers referentes a serviços da camada batch, definidos em `cluster_dev_batch.yml`.

**OBS**: Na primeira execução as imagens serão baixadas do Docker Hub, o que pode levar um tempo considerável. Nas execuções seguintes, as imagens já estarão disponíveis localmente.

É possível monitorar os containers e pará-los com os scripts `monitor_dm_dev_cluster.sh` e `stop_dm_dev_cluster.sh`, respectivamente.



## 3 - Explicação sobre o case desenvolvido


## 5 - Reprodução do Case

Um dos requisitos do case é que a solução proposta seja reproduzível. Para que tal objetivo seja alcançado as seguintes escolhas foram tomadas em relação a ferramentas.

### 5.1 - Docker

Como foi visto nas seções anteriores, esse trabalho foi construído utilizando a ferramenta docker. A definição de imagens docker torna possível que essas imagens sejam instanciadas como containers em qualquer ambiente, desde que o docker esteja instalado e requisitos mínimos de hardware sejam atendidos.

A orquestração de containers foi feita com as ferramentas Docker Compose e Docker Swarm e as definições presentes nos arquivos yml presentes no diretório `services/`.

Dessa forma o case aqui implementado pode ser reproduzido (desde que requisitos de hardware sejam atendidos) em qualquer ambiente que possua o docker instalado. Para isso, basta executar alguns comandos no terminal.

### 5.2 - Makefile

Para automatizar esse processo de execução de diferentes e inúmeros comandos no terminal, foi definido um **Makefile** na raíz desse projeto. Nesse arquivo estão definidos comandos necessários para interagir com o docker e mais alguns shell scripts localizados no diretório `scripts/`. A seguir estão listados os comandos disponíveis no Makefile.

#### Comandos disponíveis no Makefile

```bash

make build # Realiza o build das imagens docker definidas no diretório docker/


```

### 1.3 Inicialização de ambiente de Produção

Utilizando o `Docker Swarm` para subir os containers em um ambiente distribuído, foram desenvolvidos os serviços de persistência de dados e os serviços de visualização de dados.



1. **Inicialização do cluster Swarm**: Dado que os nós do cluster estão disponíveis, então o cluster pode ser inicializado com o comando:
2. **Listagem de nós do cluster Swarm**: Lista os nós do cluster Swarm e verifica status e disponibilidade dos mesmos.
3. **Deploy de stack de serviços no cluster Swarm**: O comando abaixo pode ser executado com os arquivos. Nesse projetos as stacks definidas estão são os arquivos `cluster_prod_fast.yml`, `cluster_prod_app.yml`e `cluster_prod_batch.yml`.
4. **Deleção de um stack de serviços**:
5. **Listagem de serviços deployados no cluster Swarm**:

```bash
./start_cluster.sh
docker node ls
docker stack deploy -c {stack_file_name.yml} {stack_name}
docker stack rm {stack_name}
docker service ls
```