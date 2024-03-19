# dm_v3_chain_explorer System

Nesse repositório estão implementadas e documentadas as rotinas de ingestão e processamento de dados de blockchains em tempo real desenvolvidas para o case de Data Master.

- **Badge Atual**: Data Advanced em engenharia de dados.
- **Objetivo**: Conquista da badge de Data Expert em engenharia de dados.

## 1 - Requisitos do Case

### 1.1 - Objetivo da Apresentação do Case



## 2 - Introdução ao case escolhido

O `dm_v3_chain_explorer` é um sistema de ingestão e processamento de dados de blockchains em tempo real. O sistema é composto por 3 camadas:

- **Camada Fast**: Camada de ingestão de dados em tempo real.
- **Camada Batch**: Camada de processamento de dados em batch.
- **Camada de Aplicação**: Camada com aplicações que interagem com blockchain e ferramentas de Big Data para ingestar, processar e persistir dados.

**OBS**: Nas camadas Fast e Batch, são utilizadas ferramentas de Big Data para ingestão, processamento e armazenamento de dados que estão descritos na seção 3.1. Como esse trabalho propõe a ingestão, processamento, armazenamento e uso de dados de blockchains, vale a pena fazer uma breve introdução sobre o que é um blockchain e como ele funciona.

### 2.1 - O que é um blockchain?

Abaixo estão enumerados alguns conceitos da tecnologia blockchain compilados a partir de estudos durante alguns anos. Essa breve introdução busca resumidamente descrever conceitos, fundamentos dessa tecnologia, abordando alguns aspectos da estrutura de dados Blockchain e das redes P2P.

É importante salientar que para um engenheiro de dados, o combo sistemas com tecnologia distribuída e descentralizada mais estrutura de dados é um prato cheio para aplicar conhecimentos de engenharia de dados e ainda explorar novos horizontes.

#### 2.1.1. Blockhchain como estrutura de dados

Um termo blockchain deriva de uma estrutura de dados que armazena informações de maneira encadeada, na forma de blocos. Cada bloco contém, entre outros dados um conjunto de transações e um hash que aponta para o bloco anterior. Isso garante a integridade dos dados da seguinte forma: O hash de um bloco é calculado usando os dados do próprio bloco. Então suponha que transações de um bloco da cadeia sejam modificadas. O bloco passaria a ter um hash diferente do hash anterior armazenado no bloco posterior. O website [Data Science Tools](https://tools.superdatascience.com/blockchain/hash) oferece uma ótima ilustração didática sobre o funcionamento de um blockchain.

![Figura 1: Ilustralçao de cadeia de blocos](./img/blockchain_simple.png)

#### 2.1.2. Blockhchain como rede P2P

A principal característica de um blockchain é a sua natureza descentralizada. Isso significa que não existe um servidor central validando transações, mas sim uma rede de P2P que governa o blockchain. A estrutura de dados em blocos do blockchain é armazenada em cada nó da rede P2P. Isso torna possivel que cada validar transações, minerar blocos e garantir a segurança e a integridade dos dados analisando sequências de Hash por exemplo. 

Como uma blockchain é uma estruturas de dados dinâmica dentro de uma rede P2P, um dos pontos de maior importância nesses protocolos de é o consenso, o processo pelo qual a rede escolhe quem vai minerar o próximo bloco.

Cada protocolo blockchain têm especificados entre outros parâmetros:

- Mecanismos de consenso;
- Mecanismo de validação de transações;
- Tamanho de blocos: Especificação em bytes do tamanho máximo de um bloco (Fator que influencia diretamente na escalabilidade da rede);
- Tempo de bloco: Intervalo de tempo entre a mineração de 1 bloco e outro.

<img src="./img/p2p-network-vs-server.jpg" alt="Figura 2: Ilustração Redes Server-Client e P2P" width="300" height="200">

#### 2.1.3. Blockchains públicas

Blockchains públicas são redes de blockchain onde qualquer pessoa pode ser um nó da rede. Esse tipo de blockchain é bem conveniente para esse trabalho, pois os dados de transações e contratos inteligentes são públicos e podem ser acessados. Se qualquer pessoa pode ser um nó da rede e se todos os nós possuem uma cópia do ledger, então é possível acessar os dados de um blockchain público, desde que se tenha acesso um nó da rede. A interação com um nó da rede é feita por meio de APIs oferecidas pela comunidade de desenvolvedores de cada protocolo para diferentes linguagens de programação.

#### 2.1.4. Principais protocolos de blockchain Públicos

O principal protocolo de blockchain é o **Bitcoin**, criado por Satoshi Nakamoto em 2008. Ele básicamente consiste de uma cadeia de blocos que armazena transações de sua moeda (Bitcoin). Então cada bloco contém um conjunto de transações (pessoas trocando bitcoins) e um hash que aponta para o bloco anterior. Para que 1 bloco seja minerado a rede entra em consenso sobre o minerador do bloco após esse resolver 1 problema matemático P e os outros nós validarem a prova da solução. Esse minerador é recompensado com uma quantidade de bitcoins e as transações contidas no bloco são validadas e adicionadas ao ledger. O problema P é resolvido por meio de um processo de tentativa e erro, que é chamado de proof-of-work (PoW).

O segundo protocolo de blockchain mais conhecido é o **Ethereum**, criado por Vitalik Buterin em 2015. A rede Ethereum possui as funcionalidades citadas acima, na qual 2 [endereços](https://etherscan.io/address/0x95222290DD7278Aa3Ddd389Cc1E1d165CC4BAfe5) podem trocar o token nativo do protocolo, e também a capacidade de hospedar contratos inteligentes. Os [contratos inteligentes](https://www.infomoney.com.br/guias/smart-contracts/) consistem de programas de computadores, muito similares a classes, mas que ao invés de serem instanciados, são deployados em um bloco da rede com endereço próprio. Após deployados esses contratos passam a estar disponíveis para interação. Isso permite que aplicações descentralizadas (dApps) sejam criadas dentro do protocolo.

<img src="./img/bitcoin-e-ethereum.jpg" alt="Figura 3: Bitcoin e Ethereum" width="300" height="200">

Após a Ethereum surgiram inúmeros outros protocolos de blockchain baseados na máquina virtual Ethereum, como Binance Smart Chain, Polygon, Avalanche, entre outros, herdando características e funcionalidades do Ethereum. Esse tópico tem relevância para o case proposto, pois a rede Ethereum é a rede que será utilizada para a ingestão e processamento de dados em tempo real. Porém como será demonstrado mais adiante, a arquitetura de solução proposta é genérica e pode ser aplicada a qualquer rede de blockchain EVM.

### 2.2 - Por que escolher blockchains para esse trabalho?

**Causa**: Esse case consiste fundamentalmente na apresentação de um trabalho onde possam ser avaliados conceitos e técnicas de engenharia de dados, aplicados na construção prática de um sistema. Logo, como fator essencial e primordial para o desenvolvimento de um bom trabalho, está a escolha do tema a ser abordado e consequentemente quais serão as origens dos dados, arquitetura de solução, ferramentas e tecnologias a serem utilizadas.

**Motivo**: Para esse trabalho a origem dos dados escolhida foram redes de blockchains EVM. Nessas redes, conforme descrito acima, novos blocos são minerados a cada intervalo de tempo e esses blocos contém transações. Portanto, é possível que sejam desenvolvidas soluções que possam capturar, ingestar, processar, persistir e usar esses dados para bots, dashboards, analytics, entre outras aplicações.

**Justificativa**: Alguns dos pontos que embasam a escolha de blockchains para esse case são:

- **Conhecimento**: Visto que um blockchain é fundamentalmente uma estrutura de dados que armazena informações de maneira encadeada, na forma de blocos e por natureza descentralizada, abordar esse tema é uma oportunidade de aprendizado em diferentes áreas e fortalecimento de fundamentos de engenharia de dados.

- **Nível de dificuldade**: O fato de os dados serem públicos apenas torna possível que sejam obtidos. Desenvolver um sistema que possa ingestar e processar dados de blockchains em tempo real é um desafio técnico que envolve conhecimentos de engenharia de dados, arquitetura de sistemas, segurança da informação, entre outros. Como será visto mais adiante, para resolver o desafio proposto aqui, com os recursos disponíveis, foi necessária a construção de um sistema distribuído, que envolveu o uso de ferramentas de Big Data, orquestração de containers, entre outros. E o mais importante, decisões de arquitetura de solução que envolvem trade-offs entre diferentes tecnologias e ferramentas precisaram ser tomadas.

- **Casos de uso e oportunidades reais**: Dado que blockchains possuem dados públicos e dadas também as aplicações que atualmente existem nessas redes, é possível que sejam desenvolvidas soluções para resolver problemas reais de negócio com esse sistema proposto. Dois exemplos de aplicações de contratos inteligentes são [AAVE](https://app.aave.com/) e [Uniswap](https://app.uniswap.org/swap), protocolos de [finanças descentralizadas (DeFi)](https://defillama.com/) que permitem empréstimos e trocas de tokens, respectivamente. Essas aplicações são documentadas para desenvolvedores em [Uniswap Docs](https://docs.uniswap.org/) e [AAVE Docs](https://docs.aave.com/developers).

**OBS**: Não é escopo desse trabalho detalhar o funcionamento dos contratos inteligentes citados. Porém vale a pena comentar brevemente que:

- Aave é um protocolo de empréstimos, onde os usuários podem emprestar e tomar empréstimos de tokens. É possivel prover liquidez para o protocolo e obter juros sobre os empréstimos. É possível tomar empréstimos de tokens com garantia de outros tokens.
Para o protocolo se manter saudável financeiramente, é necessário que as posições de empréstimos e liquidez provida como garantia desses empréstimos sejam balanceadas, tarefa que se torna mais dificil visto a volatividade dos preços dos tokens. Como os protocolos são agentes passivos, eles delegam a tarefa de manter a saúde financeira do protocolo, liquidando posições de risco a agentes ativos, que podem ser bots ou pessoas. Esses bots são programados para monitorar as posições de empréstimos e liquidez provida e liquidar posições de risco, obtendo lucro com isso.

O protocolo também possibilita a execução de [Flash Loans](https://etherscan.io/address/0x7a250d5630b4cf539739df2c5dacb4c659f2488d#writeContract), que são empréstimos sem garantia que devem ser pagos de volta no mesmo bloco.

- A Uniswap é uma exchange de tokens descentralizada, onde os usuários fazem swap tokens (criptomoedas). O protocolo é composto por piscinas de liquidez de pares de tokens. É possível prover liquidez para o protocolo e obter juros sobre os swaps. E também é possível fazer swaps de tokens. O interessante desse contrato está na forma como ele calcula o preço de um token em relação a outro, usando um mecanismo de [Automated Market Makers](https://academy.binance.com/pt/articles/what-is-an-automated-market-maker-amm), que permite a realização de arbitragens entre diferentes piscinas de liquidez.

Usuários da uniswap também podem executar uma funcionalidade chamada [Flash Swap](https://etherscan.io/address/0xc2e9f25be6257c210d7adf0d4cd6e3e881ba25f8#writeContract) que são swaps realizados sem garantia, ou seja, sem que o usuário tenha os tokens que está trocando. Isso é possível devido a natureza descentralizada da rede e atômica do bloco.

Esses fatores citados acima são só alguns dos que embasam a escolha de blockchains para esse trabalho. Ingestar, analisar e processar dados de blockchain pode ser uma tarefa desafiadora, mas também pode ser uma oportunidade de aprendizado e de desenvolvimento de soluções para problemas reais.

A seguir será descrita a arquitetura de solução proposta para o sistema de ingestão e processamento de dados de blockchains em tempo real.


## 3 - Arquitetura de Solução do projeto

Desenho de arquitetura:

![Arquitetura de streaming-transactions](./img/arquitetura_streaming_txs.png)


## 4 - Ferramentas utilizadas

### 4.1 Docker

Na composição de serviços desse projeto, foi utilizada a ferramenta docker para criação de containers. Essa escolha se deu pelos seguintes motivos:

- **Portabilidade**: Com o docker, é possível criar containers que podem ser executados em qualquer ambiente, independente do sistema operacional ou da infraestrutura.

- **Isolamento**: Cada container é isolado do restante do sistema, o que permite que diferentes serviços sejam executados em um mesmo ambiente sem que haja conflitos.

- **Natureza do projeto**: Na apresentação do case, se faz necessário o uso de ferramentas que são por natureza distrubuídas, como o Apache Kafka e o Apache Cassandra. O docker permite que essas ferramentas sejam executadas em containers, simulando um ambiente distribuído.

## 1.2 Orquestração de containers

Para orquestrar a execução dos containers, foram utilizadas as ferramentas `Docker Compose` e `Docker Swarm`.

### 1.2.1 Docker Compose e ambiente local

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

### 1.3 Inicialização de ambiente de Produção

Utilizando o `Docker Swarm` para subir os containers em um ambiente distribuído, foram desenvolvidos os serviços de persistência de dados e os serviços de visualização de dados.

### 1.4 Recursos computacionais usados em cluster

| Node          | IP            | Hostname                  | Usuário  | OS Version         | CPUs | Arquitetura | Model                                     | Memória RAM | Memória SWAP |
|---------------|---------------|---------------------------|----------|--------------------|------|-------------|-------------------------------------------|--------------|-------------|
| Node Master   | 192.168.15.101| `dadaia@dadaia-desktop`   | dadaia   | Ubuntu 22.04.4 LTS | 8    | x86_64      | Intel(R) Core(TM) i7-2600 CPU @ 3.40GHz   | 15866,8 MB   | 2048,0 MB   |
| Node Marcinho | 192.168.15.88 | `dadaia-HP-ZBook-15-G2`   | dadaia   | Ubuntu 22.04.4 LTS | 8    | x86_64      | Intel(R) Core(TM) i7-4810MQ CPU @ 2.80GHz | 15899,1 MB   | 2048,0 MB   |
| Node Ana      | 192.168.15.8  | `dadaia3-Lenovo-Y50-70`   | dadaia-3 | Ubuntu 22.04.4 LTS | 8    | x86_64      | Intel(R) Core(TM) i7-4720HQ CPU @ 2.60GHz | 11864,0 MB   | 0           |
| Node Arthur   | 192.168.15.83 | `dadaia2-ThinkPad-E560`   | dadaia2  | Ubuntu 22.04.4 LTS | 4    | x86_64      | Intel(R) Core(TM) i5-6200U CPU @ 2.30GHz  | 3790,3 MB    | 2048,0 MB   |

As máquinas listadas acima estão conectadas por 1 rede local.

### 1.5 Comandos Docker Swarm para gerenciar o cluster

**1. Inicialização do cluster Swarm**: Dado que os nós do cluster estão disponíveis, então o cluster pode ser inicializado com o comando:

```bash
./start_cluster.sh
```

**2. Listagem de nós do cluster Swarm**: Com o comando abaixo é possível listar os nós do cluster Swarm e verificar status e disponibilidade dos nós:

```bash
docker node ls
```

**3. Deploy de stack de serviços no cluster Swarm**: O comando abaixo pode ser executado com os arquivos 

```bash
docker stack deploy -c {stack_file_name.yml} {stack_name}
```

**OBS**: Nesse projetos as stacks definidas estão são os arquivos `cluster_prod_fast.yml`, `cluster_prod_app.yml`e `cluster_prod_batch.yml`:

**4. Deleção de um stack de serviços**:

```bash
docker stack rm {stack_name}
```

**5. Listagem de serviços deployados no cluster Swarm**:

```bash
docker service ls
```


## 2 - Arquitetura do projeto


Desenho de arquitetura:

![Arquitetura de streaming-transactions](./img/arquitetura_streaming_txs.png)