# dm_v3_chain_explorer System

Neste repositório estão implementadas e documentadas rotinas de extração, ingestão, processamento, armazenamento e uso de dados com origem em protocolos P2P do tipo blockchain, assim como definições imagens docker e arquivos yml com serviços utilizados. Esse trabalho foi desenvolvido para o case do programa Data Master.

## Sumário

1. [Objetivo do Case](#1---objetivo-do-case)
2. [Arquitetura](#2---arquitetura)
3. [Explicação sobre o case desenvolvido](#3---explicação-sobre-o-case-desenvolvido)
4. [Aspectos técnicos](#4---aspectos-técnicos)
5. [Reprodução da arquitetura e do case](#5---reprodução-da-arquitetura-e-do-case)
6. [Melhorias e considerações finais](#6---melhorias-e-considerações-finais)
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

A arquitetura técnica desse sistema é composta por diferentes camadas, cada uma com um conjunto de serviços que interagem entre si. As camadas são:

- **Camada Fast**: Camada de ingestão de dados em tempo real.
- **Camada Batch**: Camada de processamento de dados em batch.
- **Camada de Aplicação**: Camada com aplicações que interagem com blockchain.
- **Camada de Operação**: Camada com serviços necessários ao monitoramento do sistema.

Foi optado nesse trabalho pela construção de um ambiente híbrido, ou seja, usando recursos de cloud e on-premises mas com foco no on-premises.

Nesta versão os serviços de cloud utilizados se restringem ao Key Vault e ao Azure Tables, ambos serviços da Azure e de um Service Principal para autenticação.

#### 2.2.1 - Ambiente local e Docker

Apesar da opção de construir um projeto usando recursos inteiramente da cloud se apresentar, a escolha pela construção de algo local. Para definir e deployar serviços a ferramenta `docker` trás os seguintes benefícios:

1. A ferramenta é gratuita e suas imagens são portáveis, podendo esse trabalho ser reproduzível em outros ambientes locais com docker instalado.

2. As imagens docker de serviços da camada de aplicação podem, posteriormente, ser usadas para deployar os serviços em recursos de cloud para gerenciamento e orquestação de containers.

3. As imagens e serviços que representam ferramentas usadas para ingestão, processamento e armazenamento, entre outras funcionalidades, possuem serviços análogos em provedores de cloud, podendo ser migradas para esses ambientes sem grandes dificuldades.

4. A construção, gerenciamento e deploy de serviços em ambiente local é uma oportunidade de aprendizado de mais baixo nível sobre especificidades de cada serviço.

Além disso, o uso de docker possibilita que imagens possam ser instanciadas em containers, que se assemelham, nas devidas proporções, a computadores isolados, tornando a ferramenta ideal para simular um ambiente distribuído. Os containers encapsulam todo software necessário para execução de um serviço ou aplicação definidos da imagem, o que o torna portável para execução no computador do leitor ou em outros ambientes com a engine do docker instalada. As definições de imagens para esse trabalho se encontram no diretório `docker/`.

#### 2.2.2 - Serviços deployados em Compose e Swarm

Para orquestração de containers, foram utilizadas as ferramentas `Docker Compose` e `Docker Swarm`.

- **Docker Compose**: Usado para orquestrar containers em ambiente single node foi utilizado desde o início do trabalho.

- **Docker Swarm**: Devido a quantidade de containers orquestrados e recursos computacionais consumidos, foi implementado um cluster swarm para deployar os serviços em ambiente distribuído, tendo assim maior controle sobre os recursos computacionais.

As definições de serviços para essas ferramentas se encontram no diretório `services/`.

#### 2.2.3 - Camadas do sistema

Devido a quantidade de serviços orquestrados para exibir a funcionalidade completa do sistema, foi definido um sistema com diferentes camadas, cada uma com um conjunto de serviços que interagem entre si. As camadas são:

Uma visão geral dos diferentes serviços dispostos em layer que compões esse sistema está ilustrada no diagrama a baixo.

![Serviços do sistema](./img/batch_layer.drawio.png)

Esse desenho acima traz um panorama geral. Os serviços das camadas Batch, Fast e Aplicação se encontram definidas em arquivos .yml na pasta `services/` onde:

#### 2.2.3.1 - Camada Batch

Serviços relacionados a um Cluster Hadoop, junto a ferramentas que trabalham com tal cluster de forma conjunta, tais como o Apache Spark, Apache Airflow, entre outros.

- **Definições de serviços**:
  - Cluster Compose: `services/cluster_dev_batch.yml`.
  - Cluster Swarm: `services/cluster_prod_batch.yml`.

#### 2.2.3.2 - Camada Fast

serviços relacionados a um cluster Kafka e ferramentas de seu ecossistema, tais como Kafka Connect, Zookeeper, Schema Registry, o ScyllaDB, entre outros.

- **Definições de serviços**:
  - Cluster Compose: `services/cluster_dev_fast.yml`.
  - Cluster Swarm: `services/cluster_prod_fast.yml`.

#### 2.2.3.3 - Camada de Aplicação

Aplicações que interagem com a rede de blockchain para capturar os dados, ingestá-los, processa-los e armazena-los no serviços dos layers Batch e Fast.

- **Definições de serviços**:
  - Cluster Compose: `services/cluster_dev_app.yml`.
  - Cluster Swarm: `services/cluster_prod_app.yml`.

#### 2.2.3.4 - Camada de Operação

Serviços que monitoram a infraestrutura do sistema, como Prometheus, Grafana e exporters de métricas necessários para monitoramento.

TODO:

1. Imagem operações DEV (Dashes graphana)
2. Imagem operações PROD (Dashes grafana)



## 3 - Explicação sobre o case desenvolvido

### 3.1 - Histórico de desenvolvimento

Como foi o desenvolvimento desse case ao longo do tempo

### 3.2 - Temática do case

Qual é a temática do case e por que a aplicabilidade desse case pode se tornar algo maior?

## 4 - Aspectos técnicos

- **Docker**: A ferramenta docker foi utilizada para construção de imagens de serviços e orquestração de containers. As definições de imagens e serviços estão presentes no diretório `docker/` e `services/`.

- **Kafka**: O Apache Kafka foi utilizado para captura e ingestão de dados brutos da rede Ethereum. A definição de serviços para o Kafka está presente no arquivo `services/cluster_dev_fast.yml`.


## 5 - Reprodução da arquitetura e do case

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

## 6. Melhorias e considerações finais

Melhorias e considerações desse trabalho.
