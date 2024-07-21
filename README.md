# dm_v3_chain_explorer System

Neste repositório se encontra a implementação e documentação de um case de estudo desenvolvido.

Estão aqui implementadas estratégias e rotinas de extração, ingestão, processamento, armazenamento e uso de dados com origem em protocolos P2P do tipo blockchain, assim como definições imagens docker e arquivos yml com serviços utilizados. Esse trabalho foi desenvolvido para o case do programa Data Master.

## Sumário

- [1. Objetivo Geral](#1-objetivo-geral)
- [2. Introdução](#2-introdução)
  - [2.1 Estrutura de dados blockchain](#21-estrutura-de-dados-blockchain)
  - [2.2 Rede blockchain tipo P2P](#22-rede-blockchain-tipo-p2p)
  - [2.3 Redes Blockchain, Públicas e privadas](#23-redes-blockchain-públicas-e-privadas)
  - [2.4 Características de uma rede blockchain](#24-características-de-uma-rede-blockchain)
  - [2.5 Exemplos de blockchains públicas](#25-exemplos-de-blockchains-públicas)
  - [2.6 Blockchains e Contratos inteligentes](#26-blockchains-e-contratos-inteligentes)
  - [2.7 Oportunidades em blockchains públicas](#27-oportunidades-em-blockchains-públicas)
- [3. Objetivos específicos](#3-objetivos-específicos)
  - [3.1. Objetivos de negócio](#31-objetivos-de-negócio)
  - [3.2. Objetivos técnicos](#32-objetivos-técnicos)
  - [3.3. Observação sobre o tema escolhido](#33-observação-sobre-o-tema-escolhido)
- [4. Explicação sobre o case desenvolvido](#4-explicação-sobre-o-case-desenvolvido)
  - [4.1. Provedores de Node-as-a-Service](#41-provedores-de-node-as-a-service)
  - [4.2. Restrições de API keys](#42-restrições-de-api-keys)
  - [4.3. Captura de dados de blocos e transações](#43-captura-de-dados-de-blocos-e-transações)
  - [4.4. Mecanismo para Captura de Dados](#44-mecanismo-para-captura-de-dados)
  - [4.5. Mecanismo de compartilhamento de API Keys](#45-mecanismo-de-compartilhamento-de-api-keys)
- [5. Arquitetura do case](#5-arquitetura-do-case)
- [5.1. Arquitetura de solução](#51-arquitetura-de-solução)
- [5.2. Arquitetura técnica](#52-arquitetura-técnica)
- [6. Aspectos técnicos desse trabalho](#6-aspectos-técnicos-desse-trabalho)
  - [6.1. Dockerização dos serviços](#61-dockerização-dos-serviços)
  - [6.2. Orquestração de serviços em containers](#62-orquestração-de-serviços-em-containers)
- [7. Reprodução do sistema dm_v3_chain_explorer](#7-reprodução-do-sistema-dm_v3_chain_explorer)
  - [7.1. Requisitos](#71-requisitos)
  - [7.2. Clonagem de repositórios desse trabalho](#72-clonagem-de-repositórios-desse-trabalho)
  - [7.3. Reprodução do sistema usando o Docker Compose](#73-reprodução-do-sistema-usando-o-docker-compose)
- [8. Conclusão](#8-conclusão)
- [9. Melhorias futuras](#9-melhorias-futuras)
  - [9.1. Aplicações downstream para consumo dos dados](#91-aplicações-downstream-para-consumo-dos-dados)
  - [9.2. Melhoria em aplicações do repositório onchain-watchers](#92-melhoria-em-aplicações-do-repositório-onchain-watchers)
  - [9.3. Troca do uso de provedores Blockchain Node-as-a-Service](#93-troca-do-uso-de-provedores-blockchain-node-as-a-service)
  - [9.4. Evolução dos serviços de um ambiente local para ambiente produtivo](#94-evolução-dos-serviços-de-um-ambiente-local-para-ambiente-produtivo)

## 1. Introdução

Atualmente muitas tecnologias estão em alta no mercado. Contudo, para além do hype, entender conceitos e fundamentos nesses campos é promissor, pela possiblidade de oportunidades se revelarem, e enriquecedor, no âmbito do conhecimento. Nesse trabalho a tecnologia **Blockchain** é explorada como uma oportunidade de negócio.

Pois bem, o objetivo desse trabalho é stressar conceitos de engenharia de dados e áreas correlatas, como arquitetura de sistemas, segurança da informação, entre outros. A tecnologia blockchain é um componente de negócio.

Quem nunca ouviu algo como:

1. A tecnologia blockchain é disruptiva;
2. Contratos inteligentes são o futuro;
3. Dados de blockchain são públicos;
4. Circulam bilhões de dólares na forma de ativos tokenizados blockchains.

Entre outra infinidade de frases parecidas relacionadas ao tema. Mas será mesmo que tudo isso é tão verdade? Vale puxar o fio da meada.

Pois bem, temos então: **(1)** um trabalho para explorar conceitos de engenharia de dados em profundidade; **(2)** uma tecnologia disruptiva onde os dados são públicos e **(3)** circula uma quantidade significativa de capital nessas redes. Está dada a razão do porque esse trabalho foi desenvolvido. Ele consiste de uma plataforma de captura, ingestão, armazenamento e uso de dados de redes blockchain públicas e é denominado **dm_v3_chain_explorer**.

### Estrutura do documento

1. **Introdução**: Após a apresentação inicial, dada acima, é preciso introduzir ao leitor, de forma breve, sobre a tecnologia blockchain, suas características, classificações e aplicações. Essa introdução construirá as bases para o entendimento do tema e dos objetivos desse trabalho.

2. **Objetivos**: São apresentados os objetivos gerais e específicos desse trabalho. Os objetivos de negócio e técnicos são categorizados e justificados.

3. **Explicação sobre o case desenvolvido**: É dada uma explicação sobre o case desenvolvido, justificando a escolha da rede Ethereum como fonte de dados e a estratégia de captura de dados.

## 1.1. Introdução sobre blockchain

Fundamentalmente, uma blockchain, consiste em uma rede decentralizada na qual usuários transacionam entre si sem a necessidade de um intermediário. Para tanto, a tecnologia se basea em 2 componentes, a **estrutura de dados** e a **rede P2P**, ambas cunhadas também pelo termo **blockchain**.

### 1.1.1. Estrutura de dados blockchain

Estrutura que armazena blocos de forma encadeada, dando origem ao termo **blockchain**. Um bloco é uma estrutura de dados composta por:

- Metadados do bloco como por exemplo o número, hash, timestamp de quando foi minerado, quem o minerou, etc.
- Lista de transações feitas por usuários da rede persistidas no bloco.
- Hash do bloco anterior.

<img src="./img/intro/1_blocks_transactions.png" alt="Estrutura de dados Blockchain" width="80%"/>

Essa estrutura se basea de algoritmos de criptografia, como o **SHA-256**, para garantir a integridade dos dados. Isso ocorre da seguinte forma:

- Cada bloco tem seu campo `hash`, calculado a partir um algoritmo de hash e tendo como entrada os campos do bloco (lista de transações, timestamp e outros).
- Cada bloco possui também o hash do bloco anterior registrado nele.

Suponhamos que o bloco anterior seja corrompido, alterando-se o valor de uma transação por exemplo. haverá uma quebra na cadeia de blocos, ou seja, o campo `hash` do bloco anterior não baterá com o campo `hash do bloco anterior` contido no bloco atual. E esse efeito se propaga por toda a cadeia de blocos.

Portanto, com uma simples verificaçao de hashes, é possível garantir a integridade de toda a estrutura de dados blockchain. Com a ferramenta [tools.super_data_science](https://tools.superdatascience.com/blockchain/hash) é possível praticar os conceitos dessa estrutura de dados a partir de uma simulação.

### 1.1.2. Rede Peer-to-peer (P2P) Blockchain

Rede de computadores, de topologia **Peer-to-Peer** e onde nós pertencentes a ela possuem uma cópia da estrutura de dados blockchain sincronizada. Esses nós agem na rede, conforme 2 papéis distintos, **usuários** e **mantenedores**.

- **Usuários da rede**: São atores que transacionam entre si por meio de carteiras digitais. Podem trocar tokens entre si e interagir com contratos inteligentes. Para submeter uma transação a rede, é preciso ter acesso a um nó da rede, seja de forma direta ou indireta.

- **Mantenedores da rede**: São atores que mantém a rede funcionando. Eles são responsáveis por:

  - Minerar novos blocos contendo transações;
  - Validar novos blocos minerados e consenso sobre encadeá-los na estrutura de dados blockchain da rede;
  - Validar a integridade de transações contidas em blocos de toda a rede, utilizando-se dos hashes dos blocos.

<img src="./img/intro/2_p2p_networks.jpg" alt="Rede P2P blockchain" width="80%"/>

**Observação**: Para um leitor curioso, ou um engenheiro curioso, interessado em explorar conceitos engenhosos, a forma com que essa rede P2P escolhe o próximo bloco a ser minerado é um campo fértil para exploração. A rede precisa entrar em consenso sobre quem irá minerar o próximo bloco. E existem atores maliciosos nessa rede, obviamente. O mecanismo de consenso é um campo de estudo vasto e interessante. Tem como pano de fundo o famoso [Problema dos Generais Bizantinos](https://pt.wikipedia.org/wiki/Problema_dos_generais_bizantinos) e suas aplicações em sistemas distribuídos tolerantes a falhas.

Quando a rede atinge um consenso sobre qual é o novo bloco minerado, esse bloco é propagado para todos os nós da rede. E cada nó valida a integridade do bloco, garantindo que a estrutura de dados blockchain permaneça íntegra.

### 1.1.3. Redes Blockchain, Públicas e privadas

Conforme dito, redes blockchain são compostas pela estrutura de dados blockchain e por nós, que podem ser então classificados em **usuários** e **mantenedores**.
Por consequência, essas redes podem ser categorizadas de acordo com os critérios para ingresso nas mesmas.

**Blockchains públicas**:  permitem que qualquer nó ingressar nela. Assim qualquer pessoa, desde que com requisitos de hardware, software e rede satisfeitos, podem fazer parte dessa rede. Exemplos de blockchains públicas são Bitcoin e Ethereum.

**Blockchains privadas**: Redes onde existem critérios para se ingressar como nó. Essas redes são usadas por empresas para uso interno. Blockchains privadas são comumente construídas a partir de ferramentas da [Fundação Hyperledger](https://www.hyperledger.org/). O próprio DREX, projeto do Banco Central do Brasil, é um exemplo de blockchain privada, construída a partir da ferramenta Hyperledger Besu.

### 1.1.4. Características de uma Rede Blockchain

**Em sistemas distribuídos** é bem conhecido o [Teorema CAP](https://www.ibm.com/br-pt/topics/cap-theorem), o qual enuncia que é impossível garantir, simultaneamente, as 3 características: **consistência**, **disponibilidade** e **tolerância a partições**. Esse teorema é fundamentado em limitações físicas de redes de computadores, culminando em que, a certa altura, é preciso sacrificar uma dessas características para melhorar as outras 2.

De forma análoga, em **sistemas decentralizados do tipo blockchain** existe o [Trilema da Escalabilidade Blockchain](https://www.coinbase.com/pt-br/learn/crypto-glossary/what-is-the-blockchain-trilemma), enunciando que, entre **decentralização**, **segurança** e **escalabilidade**, somente é possível alcançar plenamente 2 dessas, sendo necessário sacrificar a 3ª.

De forma prática a escalabilidade de uma rede blockchain é medida em termos de **transações por segundo (TPS)**. E conforme dito, há 2 parâmetros que tem influência direta nessa medida: a frequência de mineração de blocos e o tamanho dos blocos em bytes.

- Redes P2P com muitos nós (mais decentralizadas), para garantirem segurança, sacrificam a escalabilidade. É mais fácil verificar com segurança blocos pequenos e com mais tempo, não é mesmo? O contrário também é verdadeiro. Para aumentarem a escalabilidade sacrificam a segurança.

- Redes P2P com poucos nós (menos decentralizadas), podem investir em segurança e escalabilidade. Porém, a decentralização é sacrificada. E o que é a decentralização, senão a segurança em relação a própria rede?

<img src="./img/intro/3_blockchain_trilema.png" alt="Trilema blockchain" width="70%"/>

Existem soluções para driblar esse trilema, como por exemplo as **blockchains de Layer 2**. Essas redes são construídas no topo de redes blockchain públicas, como a Ethereum, geralmente menos escaláveis. Elas então herdam a segurança e decentralização da rede base, publicando provas de seu estado na rede base, podendo assim aumentar a escalabilidade.

É importante ter esse conceitos em mente, pois fundamentam a construção de diferentes redes blockchain e a escolha de uma rede blockchain para um determinado fim. E obviamente, no sistema proposto mais a seguir, a métrica TPS é um fator crucial.

### 1.1.5. Contratos inteligentes

Quando surgiram as primeiras redes blockchain, como o Bitcoin, a única forma de transação entre usuários era a transferência de tokens entre endereços de carteiras. Em 2015, com o surgimento da rede Ethereum, foi possível se criar contratos inteligentes.

[Contratos inteligentes](https://www.coinbase.com/pt-br/learn/crypto-basics/what-is-a-smart-contract) são programas, desenvolvidos em uma linguagem de programação, que são deployados numa rede blockchain na forma de uma transação em um bloco. Eles funcionam como máquinas de estados, com métodos que podem ser chamados por usuários da rede após deployados.

Conforme esses programas são chamados, eles mudam de estado. Para o cálculo de estado da rede, as redes blockchain desenvolveram **máquinas virtuais**. A [Ethereum Foundation](https://ethereum.org/en/foundation/), criadora da rede também desenvolveu uma virtual machine open-source chamada [EVM – Ethereum Virtual Machine](https://blog.bitso.com/pt-br/tecnologia/ethereum-virtual-machine). Por ser open-source, inúmeras redes blockchain públicas e privadas passaram a usar a EVM como máquina virtual para sua própria rede.

Um exemplo de contrato inteligente e uma forma de interagir com ele seria ver o [contrato do Token USDT na rede Ethereum](https://etherscan.io/address/0xdac17f958d2ee523a2206206994597c13d831ec7#code).

<img src="./img/intro/4_smart_contract_etherscan.png" alt="Trilema blockchain" width="70%"/>

#### Curiosidade para o leitor

Com os contratos inteligentes passou a ser possível se criar aplicações descentralizadas, as chamadas **DApps**. Um tipo específico de contrato, seguindo o [padrão ERC20](https://coinext.com.br/blog/erc-20), possibilitou a criação de tokens fungíveis dentro da rede, como no contrato acima. Essa informação é importante, pois as vezes você ja ouviu falar que qualquer um pode criar uma moeda digital. E é verdade. Basta criar um contrato inteligente seguindo o padrão ERC20 e deployar na rede. Dar valor a ele ja é outra história...

É importante ter claro a diferença entre os tokens nativos da rede e os tokens criados por contratos inteligentes.

### 1.1.6. Contratos inteligentes e a Web 3.0

Na arquitetura de aplicações web convencionais é bem conhecido o modelo **Banco de Dados** -> **Back-end** -> **Front-end**. O back-end é responsável por processar as requisições do front-end, acessar o banco de dados e retornar a resposta ao front-end.

Na arquitetura **Web 3.0**, o banco dados é o estado do contrato inteligente, o back-end é o contrato inteligente e o front-end é a interface gráfica que interage com o contrato inteligente. O estado é a soma de todas as transações que foram feitas com o contrato inteligente na rede blockchain. Tal estado é calculado pela máquina virtual da rede.

Não cabe aqui explorar o quão benéfico a arquitetura acima descrita é em alguns pontos. Mas trago algumas afirmações. Caso o leitor duvide, essa será sua motivacao para explorar mais sobre o tema.

- Aplicações desenvolvidas em contratos inteligentes só vão parar de funcionar se a rede blockchain inteira parar de funcionar.
- Contratos inteligentes são imutáveis. Uma vez deployados, não é possível alterar seu código, somente lançar uma nova versão na forma de outro contrato.
- Contratos inteligentes são transparentes. Qualquer um pode ver o código fonte de um contrato inteligente.

Você ja ouviu falar de **hacks em contratos inteligentes na casa de bilhões em prejuizos**. Pois bem, o motivo está na imutabilidade dos contratos. Uma vez deployado, não é possível corrigir bugs. E por serem transparentes, qualquer um pode ver o código fonte e explorar vulnerabilidades.

### 1.1.7. Exemplos de blockchains

- **Bitcoin**: 1ª blockchain criada e tem o token nativo **BTC**. É a blockchain mais decentralizada, porém lenta e com baixa escalabilidade. Não possui capacidade de deploy de contratos inteligentes. Porém, por ser a mais decentralizada e a mais segura, e em paralelo seu token nativo ser escasso, o token é altamente usado como reserva de valor. Criada como implementação do conceito de dinheiro eletrônico peer-to-peer de [Satoshi Nakamoto](https://bitcoin.org/bitcoin.pdf).

- **Ethereum**: 1ª blockchain com possiblidade deploy e interação com contratos inteligentes. Altamente decentralizada, porém possui baixa escalabilidade. Tem como token nativo o **ETH**, usado para pagar taxas de transações efetuadas na rede e para troca entre usuários. Entre redes com contratos inteligentes é a que possui mais capital alocado em contratos inteligentes.

- **Tron, Cardano, Avalanche, Binance Smart Chain, Fantom e outras**: Blockchains de **Layer 1** que usam EVM como máquina virtual. Criadas como alternativas à Ethereum. Porém sacrificam a decentralização ou segurança da rede.

- **Polygon, arbitrum, Optimist, Base**: Blockchains de **layer 2 rodando no topo da ethereum**, e que usam naturalmente a EVM como máquina virtual. Foram criadas como solução para os problemas de escalabilidade da rede Ethereum, porém herdando a segurança e decentralização da mesma.

- **Solana e outras**: Blockchains de **Layer 1** com máquina virtual própria, diferente da EVM.

- **Blockchains Privadas**: Não é possível enunciar aqui muitas blockchains privadas. Elas se fundamentam da fundação Hyperledger, e podemos citar como exemplo de peso a rede do DREX, projeto do Banco Central do Brasil de uma rede blockchain privada entre bancos privados e o Banco Central. Nela serão desenvolvidas aplicações em contratos inteligentes para as mais diversas funcionalidades. Opera usando o Hyperledger Besu, compatível com a EVM.

## 1.2. Oportunidades a serem exploradas em Redes Blockchain

Em redes circula uma quantidade significativa de capital. Este circula na forma de transações que podem ser:

- Transferência de tokens entre endereços de carteiras;
- Interação com contratos inteligentes;

Conforme visto os dados são públicos e podem ser explorados. A seguir são apresentadas algumas oportunidades de negócio que a exploração de dados de redes blockchain públicas trazem.

### 1.2.1. Monitoração de transações entre endereços de carteiras

A forma mais simples de transação em uma rede blockchain é a transferência de token nativo da rede entre endereços de carteiras.

- **Usuário 1** ENVIA **Quantidade X** de tokens nativo, no caso da Ethereum o `ETH`, para **Usuário 2**;

A monitoração de transações entre usuários tem muitas aplicações. Uma delas é a identificação de padrões de transações entre usuários. Esses padrões podem ser usados para identificar fraudes, lavagem de dinheiro, ou por outro lado oportunidades de negócio.

#### Exemplo relativo a segurança e compliance

Existem inúmeros casos em que [hackers exploram vulnerabilidades em contratos inteligentes para roubar tokens, causando prejuizos na casa de bilhões](https://br.cointelegraph.com/news/defi-exploits-and-access-control-hacks-cost-crypto-investors-billions-in-2022-report). Quando um hacker rouba tokens de um contrato inteligente, ele precisa transferir esses tokens para outros endereços, converter o token para outros, entre outras artimanhas, a fim de acobertar a origem criminosa. Para enfim vendê-los em alguma corretora e realizar o lucro da ação criminosa.

Se uma instituição financeira negocia tokens roubados, ela pode ser responsabilizada por lavagem de dinheiro da parte de agentes reguladores. Portanto, monitorar transações entre endereços de carteiras pode ser uma forma de identificar transações suspeitas e evitar prejuízos.

O meio para isso é a captura de dados de transações em tempo real, a fim de identificar esses atores criminosos.

### 1.2.2. Monitoração de interações com contratos inteligentes

Conforme visto, contratos inteligentes são programas deployados numa rede blockchain por meio de uma transação e então disponíveis para interação com usuários da rede. Essas interações se dão por meio de transações em que o usuário chama um método do contrato inteligente.

Se um contrato inteligente é um programa, bem, ele pode ser construído para os mais diversos fins. E não é diferente. Entre as principais aplicabilidades de contratos inteligentes estão:

- **Finanças descentralizadas (DeFi)**: Aplicações financeiras que permitem usuários pegar empréstimos, trocar tokens, entre outras funcionalidades, sem a necessidade de um intermediário. Exemplos de aplicações DeFi são a Aave e Uniswap.

- **Jogos e NFTs**: Lembra daquele jogo onde você pode comprar e vender um itens únicos para outro jogador? Ou de qualquer outro ativo digital que deveria ser único mas na internet é copiável? Bem, os NFTs são a solução para isso. E eles são contratos inteligentes.

Pois bem, todas essas aplicações são alcançadas por meio de transações na rede. Logo, se todas as transações da rede em que os contratos foram deployados são monitoradas, é possível identificar padrões de interações com contratos inteligentes, obter insights sobre o que está acontecendo na rede e se beneficiar desse conhecimento.

Oportunidade de negócio geralmente se traduz em oportunidade de ganho de capital. Em contratos inteligentes do tipo DeFi existe um **alto valor de capital alocado (TVL - Total Value Locked)**.

- Em [DeFi Llama Chains](https://defillama.com/chains) é possível ver o quanto capital está alocado em contratos inteligentes deployados nessa rede.
- Em [DeFi Llama Contracts](https://defillama.com/) é possível ver uma lista de DApps (contratos inteligentes) e o volume de capital retido nessas aplicações.

#### Exemplo de Aplicabilidade de capturar dados de redes blockchains em tempo real

Vejamos o seguinte cenário. Um hacker descobre uma vulnerabilidade em um contrato inteligente. Começa ele então a roubar tokens do mesmo. Esse roubo se dará, conforme mencionado, por transações na rede onde o hacker interage com o contrato. Na grande maioria dos casos essas transações maliciosas se dão em muitas transações pequenas, a fim de acobertar a origem criminosa.

Com um sistema que capture dados das transações de uma rede em tempo real, é possível identificar padrões de transações suspeitas e alertar sobre possíveis hacks. E não só. É possível identificar o padrão da transação fraudulenta e reproduzi-la, a fim de roubar tokens do contrato inteligente. Existem empresas de segurança especializadas nisso. Detectam um hack, reproduzem o hack concorrentemente ao próprio hacker e devolvem os tokens roubados ao dono posteriormente.

## 1.3. Estudo de caso sobre 2 contratos inteligentes

Vamos explorar brevemente 2 contratos inteligentes da rede Ethereum, a fim de exemplificar outras oportunidades de negócio que a exploração de dados dessas redes trazem e o quão valiosos esses dados podem ser.

- **[AAVE Borrowing and Lending](https://app.aave.com/)**: Aplicação decentralizada que permite usuários pegar empréstimos em criptomoedas, usando outras criptomoedas como garantia.
- **[Uniswap DEX](https://app.uniswap.org/?intro=true)**: Aplicação decentralizada que permite usuários trocar tokens entre si, sem a necessidade de um intermediário.

As 2 aplicações acima são exemplos de **aplicações DeFi (Finanças descentralizadas)**. Foram desenvolvidas na rede Ethereum e são contratos inteligentes. A seguir são apresentadas as oportunidades de negócio que a exploração de dados desses contratos inteligentes trazem.

### 1.3.1. Exchange Decentralizada UNISWAP

A [Uniswap](https://uniswap.org/developers) é um conjunto de contratos inteligentes que funcionam como uma aplicação decentralizada para **troca de tokens ERC20**. Em outros termos, é uma **exchange decentralizada**. O contrato principal possui o padrão factory para criação de contratos do tipo **piscinas de liquidez**.

**Contrato de piscina de liquidez**: Esses contratos são definidos por um par de tokens ERC20. Usuários da rede podem:

- Fornecer liquidez ao contrato, depositando o par de tokens nele e objetivando retorno financeiro em taxas cobradas a usuários que trocam tokens;
- Trocar tokens entre si, pagando taxas de troca.

Lembra que foi dito que qualquer pessoa pode criar 1 token ou uma moeda digital? Mas dar valor a esse token ja é outra história? Pois bem, se um usuário cria um token e então cria uma piscina de liquidez para esse token, o atrelando ao token par, por exemplo o token WETH. Ao fornecer liquidez a essa piscina, ele está dando valor ao token. Pois ele está permitindo que o token seja trocado por outro token, no caso o WETH.

**Cálculo de preço**: Para o cálculo de preço de um token em relação a outro, em uma piscina de liquidez, é usado um mecanismo chamado de [AMM - Automated Market Maker](https://academy.binance.com/pt/articles/what-is-an-automated-market-maker-amm). Um AMM tem por objetivo **regular** o preço de um token em relação a outro e mantendo a paridade com o mercado externo. O contrato inteligente é um agente passivo. Ele não tem a capacidade de regular o preço dos tokens. Ele é regulado pelos usuários que interagem com ele.

O **mecanismo de AMM usado pela Uniswap** é fundamentado em> Numa piscina de liquidez o **produto da quantidade de um par de tokens X e Y deve ser constante**.

**Exemplo:**

- 1 piscina possui 10 WETH e 10 SDM em liquidez. O produto deve ser constante = 100 WETH x SDM ao final de toda transação de troca.
- Se um usuário deseja trocar 1 WETH por SDM nessa piscina, ao final da da transação a piscina deve ter 11 WETH e 9,09 SDM.
- Quanto mais a relação entre WETH e SDM se desequilibra, mais caro é o token que está em menor quantidade.
- Contudo, o preço dos 2 ativos sofre uma flutuação que diverge do preço praticado pelo mercado em relação àqueles 2 tokens.
- Portanto, nessas flutuações aparecem oportunidades de [arbitragem](https://www.kraken.com/pt-br/learn/what-is-uniswap-uni).
- Pode-se comprar do token que flutuou para cima por um valor mais baixo no mercado e troca-lo na piscina de liquidez com valor maior, realizando-se lucros.

No exemplo acima fica evidente como esse tipo de contrato inteligente se mantém em funcionamento. Ele precisa de 3 atores:

- Provedores de liquidez para piscinas de par de tokens;
- Usuários do protocolo que trocam tokens;
- Operadores de arbitragem que mantém o preço dos tokens em equilíbrio com o mercado.

Portanto, monitorar transações de swap entre tokens ERC-20 em contratos da Uniswap pode fornecer informações valiosas para operar **arbitragem**.

### 1.3.2. AAVE Borrowing and Lending

A [Aave](https://docs.aave.com/developers) é uma aplicação que realiza empréstimos de criptomoedas. Usuários podem realizar de forma simples 2 ações nesse protocolo.

- **Depositar**: Usuários depositam um token X no contrato inteligente, provendo liquidez ao contrato para aquele token.
- **Borrow**: Usuários pegam emprestado um token Y, usando o token X depositado como garantia.

Quando os preços dos tokens flutuam, é possível que o valor do empréstimo fique abaixo do valor da garantia, deixando o protocolo em risco. Para evitar isso, a Aave usa um mecanismo de liquidação.

**Exemplo:**

- Um usuário deposita 15 WETH como garantia na AAVE.
- Ele passa a poder pegar emprestado o valor de 10 WETHs em outros tokens, por exemplo 10 SDM.
- O usuário pega emprestado então 10 SDM, que ele vende no mercado. Ele pagará taxas por esse empréstimo.
- Supondo que o valor de WETH em relação ao SDM caia 30%:
  - O valor necessário em garantia passa a ser 13 WETH.
  - Porém o valor da garantia depositado é de 10 WETH.

O contrato inteligente da Aave precisa de um mecanismo para liquidar o empréstimo, caso o valor da garantia fique abaixo do valor do empréstimo.

Para isso é possivel que usuários comuns monitorem os empréstimos do protocolo e realizem operações de liquidação, obtendo lucro com isso. Além de obter lucros eles mantém o protocolo Aave saudável. [Em Aave - Liquidations](https://docs.aave.com/developers/guides/liquidations) é possível compreender melhor o mecanismo de liquidação.

Na Aave é ainda possível realizar uma transação de empréstimo sem garantia, denominada **[Flash Loan](https://docs.aave.com/faq/flash-loans)**. Devido a arquitetura da rede e a forma com que o contrato é implementado, é possível pegar tokens emprestados, sem dar garantia, desde que se pague o empréstimo no mesmo bloco. Isso é devido a característica de atomicidade. Se um flash loan que deve ser pago no mesmo bloco não for pago, a transação é revertida.

**Conclusão**: É possível realizar arbitragem e liquidações, e com isso obter retornos financeiros, sem grande capital inicial investido.

1. Com um mecanismo de monitoramento da rede e dos contratos, é possível identificar as oportunidades de arbitragem ou liquidação;
2. Com o uso de flash Loan é possível levantar o capital necessário para realizar a operação de liquitação ou arbitragem;
3. Após a operação ser realizada, o Flash Loan é pago e o lucro é obtido. Caso a operaçao não seja bem sucedida, o empréstimo e revertido.

## 1.4. Nota sobre a introdução acima e esse trabalho

Foram explorados muitos conceitos acima. Muitos desses complexos e que demandam um estudo mais aprofundado. Porém, a intenção foi apresentar ao leitor as bases sobre a tecnologia blockchain, suas características, classificações e aplicações. Entendê-las, mesmo que de maneira superficial, é fundamental para a compreensão do sistema proposto a seguir, de sua arquitetura e dos desafios que ele apresenta. E por fim, apresentar oportunidades de negócio que a exploração de dados de redes blockchain públicas trazem.

Dados esses fatos é possível então construir uma lista de objetivos gerais e específicos para construção de um sistema que capture, ingeste, processe, persista e utilize dados de redes blockchain públicas.

## 2. Objetivos específicos

A introdução acima fundamenta os objetivos específicos desse trabalho. O objetivo final desse trabalho é sua submissão para o programa Data Master, e posterior apresentação do mesmo à banca de Data Experts. Nessa apresentação serão avaliados conceitos e técnicas de engenharia de dados, entre outros campos da tecnologia correlacionados, aplicados na construção prática deste sistema entitulado **dm_v3_chain_explorer**, que tem o propósito de capturar, ingestar, processar, persistir e utilizar dados de redes blockchain públicas.

### 2.1. Objetivos de negócio

Em resumo à introdução apresentada, as 2 proposições abaixo justificam resumidamente em termos de negócio a escolha do tema abordado nesse trabalho. São elas:

**Proposição 1**: É sabido que protocolos P2P do tipo blockchain são uma tecnologia nova e complexa. Esses protocolos são usados para:
  
- transações entre usuários de uma rede sem a necessidade de um intermediário.
- Interação com contratos inteligentes deployados na rede, para os mais diversos fins, desde finanças descentralizadas (DeFi) até jogos e NFTs.

**Dado** o grande volume de capital circula nessas redes, através de transações e interações com contratos inteligentes, **então** é possivel que haja oportunidades de negócio para empresas que desejam explorar esses dados.

**Proposição 2**: Redes P2P públicas têm os dados públicos pelos seguintes motivos:

- Por a rede é descentralizada, qualquer pessoa pode fazer parte dela, desde que atenda aos requisitos de hardware, software e rede.
- Todos os nós da rede possuem uma cópia da estrutura de dados blockchain sincronizada, de forma que a rede possa validar a integridade das transações contidas em todos os blocos. **Por consequência**, é possível se obter dados de transações e interações com contratos inteligentes dessas redes de forma direta, caso se tenha acesso a um nó da rede.

**Conclusão**: Com as proposições acima, é possível se inferir que a captura, ingestão, armazenamento e uso desses dados pode trazer oportunidades de negócio para empresas que desejam explorar esses dados. Para alcançar esses objetivos, é preciso implementar um sistema capaz de capturar, ingestar, processar, persistir e utilizar dados da origem mencionada.

### 2.2. Objetivos técnicos

O sistema **dm_v3_chain_explorer** tem como objetivos tecnicos:

- Captura de dados brutos de redes de blockchain públicas que usam EVM com máquina virtual.
- Captura de dados de estado em contratos inteligentes.
- Ser um sistema de captura agnóstico à rede de blockchain, mas restrito a redes EVM.
- Minimizar latência e números de requisições, e maximizar a disponibilidade do sistema.
- Criar um ambiente reproduzível e escalável.
- Armazenar e consumir dados pertinentes a operação e análises em bancos analíticos e transacionais.
- Possuir componentes que possam monitorar o funcionamento do mesmo (dados de infraestrutura, logs, gerenciamento de recursos, etc).

Para alcançar tais objetivos, como será explorado mais adiante, um grande desafio apareceu e é talvez o ponto mais complexo desse trabalho. A maneira de capturar esses dados, através da interação com provedores de nós blockchain-as-a-service e API keys.

### 2.3. Observação sobre o tema escolhido

Dado que a tecnologia blockchain não é assunto trivial e também não é um requisito especificado no case, apesar da introdução feita acima, no corpo principal desse trabalho evitou-se detalhar o funcionamento de contratos inteligentes e aplicações DeFi mais que o necessário para o entendimento desse sistema. 

Porém, é entendido pelo autor que, apesar de não ser um requisito especificado no case, inúmeros conceitos aqui abordados exploram com profundidade campos como:

- Estruturas de dados complexas (o próprio blockchain);
- Arquiteturas de sistemas distribuídos e descentralizados;
- Conceitos relacionados a finanças.

Portanto, a escolha desse tema para case é uma oportunidade de aprendizado e de aplicação de conhecimentos de engenharia de dados, arquitetura de sistemas, segurança da informação, entre outros.

## 3. Explicação sobre o case desenvolvido

Foi escolhido para esse trabalho o uso da rede Ethereum como fonte de dados. Isso é justificado na introdução e objetivos acima, sendo os fatores de peso:

- Capital retido na rede Ethreum;
- Compatibilidade de aplicações entre diferentes blockchains baseadas na EVM.

Conforme visto, para se obter dados de uma rede blockchain diretamente, é necessário possuir acesso a um nó pertencente a tal rede. Com isso, 2 possibilidades se apresentam: **(1)** possuir um nó próprio e **(2)** usar um nó de terceiros.

Devido aos requisitos de hardware, software e rede necessários para deploy de um nó, seja on-premises ou em cloud, foi escolhido nesse trabalho o uso de **provedores de Node-as-a-Service ou NaaS**.

## 3.1. Provedores de Node-as-a-Service

Provedores de NaaS são empresas que fornecem acesso a nós de redes blockchain públicas. Alguns exemplos são **Infura** e **Alchemy**. Esses provedores, como modelo de negócio, fornecem API keys para interação com os nós.

<img src="./img/intro/4_bnaas_vendor_plans.png" alt="4_bnaas_vendor_plans.png" width="100%"/>

Porém, esses provedores restringem a quantidade de requisições, de acordo com planos estabelacidos (gratuito, premium, etc.) que variam o preço e o limite de requisições diárias ou por segundo permitidas.

Foi optado pelo **uso de provedores NaaS**. Contudo, devido às limitações de requisições por segundo e diárias, foi preciso criar um mecanismo sofisticado para captura de todas as transações em tempo real. Por se tratar um desafio técnico, reduzir o custo para captura desses dados a zero virtualmente, satisfazendo os objetivos mencionados se mostra um caminho interessante.

## 3.2. Restrições de API keys

As requisições em nós disponibilizados por um provedores NaaS são controladas por meio de API Keys. Para o provedor infura temos as seguintes restrições para 1 API Key gratuita:

- Máximo de **10 requests por segundo**;
- Máximo de  **100.000 requests por dia**.

Na rede Ethereum, um bloco tem tamanho em bytes limitado e é minerado em média a cada 8 segundos. Cada bloco contém em média 250 transações. Isso resulta em:

- **2,7 milhões de transações por dia**;
- **31 transações por segundo**.

As limitações acima impõem um desafio. Como será visto a diante, o mecanismo **para se capturar n transações de um bloco recém-minerado** exige que sejam feitas em média **n requisições** sejam feitas. Usando o plano gratuito, claramente é necessário o uso de várias API Keys.

Porém o gerenciamento de uso dessas API Keys, que possuem recursos limitados, buscando manter a disponibilidade e confiabilidade do sistema traz a necessidade de um mecanismo engenhoso. Aqui então ela se apresenta.

## 3.3. Captura de dados de blocos e transações

Para capturar dados de blocos e transações da rede em tempo real é usada a [Biblioteca Web3.py](https://web3py.readthedocs.io/en/stable/). Ela fornece uma interface para interação com nós de redes blockchain compatíveis com EVM. Entre as várias funções disponíveis, 2 são de interesse para esse trabalho:

**get_block('latest')**: Retorna um dicionário com os **dados e metadados do bloco** e uma **lista de hash_ids** de transações pertencentes ao último bloco minerado.

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

As 2 funções mencionadas trabalhando em conjunto são o suficiente para obter dados de transações recém mineradas. Porém, é necessário que as rotinas que se utilizem delas trabalhem de forma integrada e em cooperação.

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

Nessa seção está detalhada a arquitetura do sistema **dm_v3_chain_explorer**. Na seção acima foram detalhados mecanismos para captura e ingestão do dados, bem como outros componentes usados também necessários para o funcionamento do sistema. 

O objetivo aqui é ver como esses componentes se encaixam e como o sistema funciona como um todo. Essa seção está dividida em 2 partes:

- **Arquitetura de solução**: Descrição de alto nível de como o sistema funciona para captura e ingestão de dados no Kafka. São descritos alguns componentes e seus papéis no sistema.

- **Arquitetura técnica**: Descrição detalhada de como os componentes do sistema se comunicam entre si e com serviços auxiliares, bem como os mesmos são deployados,orquestrados e monitorados.

## 4.1. Arquitetura de solução

O desenho abaixo ilustra como a solução para captura e ingestão de dados da Ethereum, e em tempo real funciona.

![Arquitetura de Solução Captura e Ingestão Kafka](./img/arquitetura/1_arquitetura_ingestão_fast.png)

Os componentes dessa solução são:

- **Apache Kafka**: Plataforma de streaming distribuída que permite publicar e consumir mensagens em tópicos. É altamente escalável e tolerante a falhas. É o backbone do sistema Pub-Sub.
- **Redis**: Banco de dados chave-valor em memória usado para armazenar dados sobre uso de API KEYs.
- **Scylla**: Banco de dados NoSQL altamente escalável e tolerante a falhas usado para armazenar dados sobre uso de API KEYs.
- **Azure Key Vault**: Serviço de segredos da Azure usado para armazenar as API Keys.
- **Apache Spark**: Framework de processamento de dados em tempo real usado para monitorar o uso das API Keys.
- **Jobs implementados em python Python**: Esses jobs são responsáveis por capturar, classificar e decodificar os dados usando as ferramentas mencionadas acima. Executam em containers docker.
- **Kafka Connect**: Ferramenta usada para conectar o Kafka a diferentes fontes de dados. Nesse caso, o Kafka Connect é usado para envio dos dados de tópicos do Kafka para outros sistemas.

## 4.2. Arquitetura Técnica

Esse trabalho utiliza inúmeros serviços e ferramentas para captura, ingestão, processamento e persistência de dados. De forma a organizar esses serviços, eles foram divididos em camadas. Cada camada é responsável por um conjunto de serviços que realizam tarefas específicas no funcionamento do **dm_v3_chain_explorer**.

- **Camada de operação**: Serviços que realizam telemetria dos recursos computacionais da infraestrutura utilizada pelo sistema.
- **Camada de aplicação**: Aplicações construídas em Python e deployadas em containers que realizam a captura dos dados na rede Ethereum e persistem no Apache Kafka.
- **Camada Fast**: Serviços auxiliares utilizados pela camada de aplicação para captura e ingestão de dados em tempo real, tais como Redis, Spark, Kafka, etc.
- **Camada Batch**: Serviços relacionados a uma arquitetura de big data, como Hadoop, Hive, etc.

Os serviços das camadas **Fast**, **Batch** e de **Operações** são aqui também **deployados em containers docker**. Em soluções produtivas, esses serviços podem ser deployados em máquinas virtuais, kubernetes ou mesmo em serviços gerenciados de cloud, cada alternativa tendo suas vantagens e desvantagens. Porém, para finalidade de um protótipo, o uso de containers é mais que suficiente.

Além dos serviços deployados em containers docker, é utilizado também recurso em cloud **Azure Key Vault** para armazenamento das API Keys como secrets.

### 4.2.1. Ambientes de Orquestração de Containers

Para orquestração de containers, foram utilizadas as ferramentas **Docker Compose** e **Docker Swarm**.

### 1. Ambiente de desenvolvimento

O **Docker Compose** é usado para orquestrar containers em um único host. O uso de bind mounts para compartilhar volumes entre o host e o container, facilita o desenvolvimento e testes. E o `docker-compose.yml` trás facilidade, agilidade e reprodutibilidade para deploy do conjunto de serviços em containers. Definamos o deploy de serviços em um único host como **single-host** e consideremos esse como o ambiente de desenvolvimento para o sistema **dm_v3_chain_explorer**.

Esse trabalho utilizou um computador pessoal como host para deploy dos serviços em containers docker para desenvolvimento. Porém, pela quantidade de serviços e para fins de escalabilidade, foi explorado o uso de **Docker Swarm** para deploy dos serviços em múltiplos hosts.

### 2. Ambiente de produção

O **Docker Swarm** é usado para orquestrar containers em múltiplos hosts. Ele é também uma ferramenta nativa do Docker e pode ser usado para deploy de serviços em containers em ambiente produtivo, onde a alta disponibilidade e escalabilidade são necessárias. O docker swarm também usa arquivos yml de configuração, similares ao docker-compose, para definir o deploy de serviços em múltiplos hosts na forma de **Stacks**.

Para esse trabalho foi montado um cluster Swarm com 4 máquinas, sendo um nó manager e 3 nós workers. Assim é possível distribuir as cargas de trabalho entre os nós e garantir a alta disponibilidade do sistema.

- **Nó Manager**: Host **dadaia-desktop** com 16GB de RAM e 8 CPUs e 256 GB de armazenamento SSD.
- **Nó Worker 1**: Host **dadaia-HP-ZBook-15-G2** com 16GB de RAM e 8 CPUs e 256 GB de armazenamento SSD.
- **Nó Worker 2**: Host **dadaia-server** Laptop com 12GB de RAM e 8 CPUs e 256 GB de armazenamento SSD.
- **Nó Worker 3**: Host **dadaia-server-2** Computador Laptop com 4GB de RAM e 8 CPUs e 256 GB de armazenamento em Hard Disk.

![Cluster Swarm Local](./img/arquitetura/2_cluster_swarm_nodes.png)

A medida que as camadas são descritas, desenhos representando a distribuição desses serviços em ambiente **single-host** e **multi-host** serão apresentados.

### 4.2.1. Camada de operação

Na camada de operação estão definidos serviços necessários para realizar telemetria e monitoramento de recursos da infraestrutura utilizados pelo sistema **dm_v3_chain_explorer**. Esses serviços são:

- **[Prometheus](https://prometheus.io/)**: Serviço usado para coleta de logs e métricas utilizadas na telemetria e monitoramento;
- **[Grafana](https://grafana.com/)**: Serviço usado para visualização de logs e métricas coletadas pelo Prometheus, provendo dashboards para monitoramento;
- **[Prometheus Agents e Exporters](https://prometheus.io/docs/instrumenting/exporters/)**: Serviços responsáveis por coletar métricas de enviar para o Prometheus. Os agentes utilizados nesse trabalho foram:
  - **[Node exporter](https://prometheus.io/docs/guides/node-exporter/)**: Agente para coletar dados de telemetria do nó em específico.
  - **[Kafka exporter](https://danielmrosa.medium.com/monitoring-kafka-b97d2d5a5434)**: Agente para coletar dados de telemetria do kafka.
  - **[Cadvisor](https://prometheus.io/docs/guides/cadvisor/)**: Agente para coletar dados de telemetria do docker.

Quando deployados em ambiente de desenvolvimento, os serviços dessa camada são deployados em um único host. Uma ilustração dessa distribuição é mostrada abaixo.

![Operational Layer Single Host](./img/arquitetura/4_ops_services_local.png)

Na figura acima 2 pontos são importantes:

- As métricas coletadas pelos exporters em suas fontes (server, kafka, docker) nos fluxos das **setas verdes**.
- Os exporters coletam essas métricas e as enviam para o Prometheus, conforme fluxo das **setas laranjas**.
- O Grafana consome essas métricas do Prometheus e as exibe em dashboards, conforme fluxo das **setas azuis**.

Quando deployados em ambiente de produção (cluster swarm), os containers são instanciados em múltiplos hosts. Logo, os exporters **cadvisor** e **node exporter** são deployados em cada nó do cluster Swarm, de forma a monitorar o docker daquele nó e as métricas daquele nó.

O **kafka exporter** precisa ser deployado em apenas um nó, o nó, desde que tenha conexão de rede com os brokers do kafka. Uma ilustração dessa distribuição é mostrada abaixo.

#### Observação

Para deploy dos serviços foi feita segregação de redes. Os seviços referentes a camada de operação estão em uma rede chamada **dm_cluster_dev_ops**. Porém, o serviço **Kafka Exporter** está também attachado a rede **dm_cluster_dev_fast** para que possa se comunicar com o Kafka. Na figura abaixo o perímetro em azul representa a rede **dm_cluster_dev_fast** e o perímetro em verde a rede **dm_cluster_dev_ops**.

![Operational Layer Multi Host](./img/arquitetura/5_compose_ops_multinode.png)

### 4.2.2. Camada Fast

Nessa camada estão definidos os serviços utilizados para ingestão de dados em tempo real e que trabalham em conjunto com os Jobs implementados na camada de aplicação. Os serviços dessa camada são:

- **Brokers do Apache Kafka**, usados como backbone de dados para fluxos de dados downstream e para comunicação entre Jobs;
- **Apache Zookeeper** utilizado por cluster de brokers do Kafka para gerenciamento de metadados e sincronização entre brokers;
- **Confluent Control Center**: Serviço com interface gráfica para visualização de tópicos, kafka clusters, consumer groups e cluster de kafka-connect.
- **Confluent Kafka Connect**: Integra o Apache Kafka às mais diferentes plataformas através de conectores do tipo sources e sinks já implementados.
- **Confluent Schema Registry**: Serviço usado para armazenar e validar schemas de dados em tópicos do Kafka.
- **ScyllaDB**: Database No-SQL que permite alto throughput de operações de escrita, é por natureza distribuído de forma uniforme e pode ser escalado para atuar de forma global. Usado para update em tabela de consumo de API Keys, para que jobs tenham ciencia de chave e sua utilização em requests no tempo.
- **Redis**: Banco de dados chave-valor usado para controle de consumo de API Keys em jobs de streaming, de forma a garantir que cada API key seja usada por somente um Job a determinado instante, atuando como um semáforo.
- **Apache Spark**: Engine de processamendo de dados. Usado para monitorar o uso de API Keys e atualizar a tabela no ScyllaDB.

A abaixo estão representados os serviços das camadas de **operações** e camada **fast** em ambiente **single-host**.

![Fast Layer Single Host](./img/arquitetura/6_ops_fast_services_local.png)

Os serviços acima deployados em ambiente de produção (cluster Swarm) são distribuídos conforme abaixo.

![Fast Layer Multi Host](./img/arquitetura/7_ops_fast_services_multihost.png)

### 4.2.3.  Camada de aplicação

Nessa camada estão definidas:

- Aplicações escritas em python para interação com blockchains do tipo EVM e plataforma de dados.
- Aplicação Spark Streaming para monitoramento de consumo de API Keys.

Como informado anteriormente, as aplicações são deployadas em containers docker e interagem com os serviços da camada **Fast**. A ilustração abaixo mostra a distribuição desses serviços em ambiente **single-host**.

![Application Layer Single Host](./img/arquitetura/8_app_services_single_host.png)

#### Observação sobre aplicações e repositórios desse trabalho

As aplicações desenvolvidas estão encapsuladas em imagens docker para serem instanciadas em containers. Devido à conveniência no gerenciamento de imagens, cada imagem docker produzida para esse trabalho foi organizada em um repositório diferente.

Esses repositórios estão na **organização Dadaia-s-Chain-Analyser** no github. O critério para segregar as funcionalidades em um repositório foi a tecnologia usada, algo que influencia no peso da imagem. E também certo escopo de funcionalidade.

Com diferentes repositórios é possível também definir workflows de CI-CD para build e deploy das imagens usando o **github actions**. Por esse motivo existem 4 repositórios relacionados a esse trabalho.

- [dm_v3_chain_explorer](https://github.com/marcoaureliomenezes/dm_v3_chain_explorer): Repositório central onde estão definidos conjunto de serviços e forma de orquestra-los para alcançar objetivos do sistema.

- [Offchain-watchers](https://github.com/Dadaia-s-Chain-Analyser/offchain-watchers): Repositório composto por rotinas que usam a **biblioteca Web3.py** para ingestão dos dados de transações e blocos de uma rede blockchain.

- [Onchain-watchers](https://github.com/Dadaia-s-Chain-Analyser/onchain-watchers): Repositório composto por rotinas que usam **framework Brownie** para interação com contratos inteligentes e obtenção de estados dos mesmos, com o objetivo de ingestá-los no sistema.

- [Onchain-actors](https://github.com/Dadaia-s-Chain-Analyser/onchain-actors): Repositório composto por rotinas que usam a **framework Brownie** para realizar transações em blockchains. São a ponta da linha do sistema e estão habilitados a realizar swaps entre outras interações em contratos inteligentes específicos.

#### Observação sobre as aplicações

As aplicações desenvolvidas nesse trabalho são construídas em python e encapsuladas em imagens docker. Dessa forma são portáveis e podem ser instanciadas em qualquer ambiente com a engine do docker instalada. Assim, em caso de necessidade de deploy em ambiente de cloud, as imagens podem ser usadas para instanciar containers em cloud, usando serviços de orquestração de containers como **ECS**, **EKS**, **AKS** ou **GKE**.

### 5.3.2. Camada Batch

Nessa camada estão relacionados serviços necessários para armazenamento e processamento de dados em big data e outras ferramentas necessárias para que pipelines batch sejam definidos.

### I) Apache Hadoop

Conjunto de serviços que compõem o hadoop e algumas ferramentas de seu ecossistema. Um cluster hadoop é composto pelos seguintes sistemas:

- **Hadoop Namenode**: Mantém controle de metadados, logs e outros dados relacionados ao cluster e ao HDFS. Um cluster hadoop pode ter 1 namenode e eventualmente também um namenode secundário em estado de standby. Este tem por função assumir o lugar do namenode primário, caso necessário.

- **Hadoop Datanodes**: Armazenam dados do cluster e atuam em conjunto com o **namenode** para formar o HDFS (hadoop Distributed File System). Um cluster Hadoop pode ter 1 ou mais datanodes, o que permite a escalabilidade horizontal em volume de dados a serem armazenados.

- **Resource Manager e Node managers**: Atuam em conjunto para gerenciar alocação de recursos de processamento no cluster Hadoop. Esse processamento se dá por meio de jobs de **Map reduce**,  jobs do **Apache Spark gerenciado pelo Yarn**, entre outros. 
  
  - Os **node managers** são instanciados em cada nó do cluster de forma a monitorar o uso de recursos naquele nó.
  - O **resource manager** atua como um orquestrador na alocação dos recursos para processamento nesse cluster, trocando informações com os **node managers**. Uma referencia mais completa sobre o [YARN pode ser vista aqui.](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/YARN.html)

- **History Server**: Serviço utilizado para armazenar dados referentes a execução de jobs de processamento no cluster hadoop.

O apache hadoop nesse trabalho é usado como data lake, onde chegam os dados inicialmente armazenados em tópicos do Kafka, por meio de um conector d otipo SINK do **kafka connect** e, futuramente de batches (processamento de jobs no airflow).

### II) Apache Hive

O hive é um sistema de Data Warehouse construída no topo do Apache Hadoop. É usado para fornecer uma camada de abstração sobre dados no data lake armazenados no HDFS. O hive permite a execução de queries em dados armazenados no HDFS. Esses dados são organizados em databases e tabelas, e consultados por meio de uma linguagem de query chamada HQL, similar ao SQL. O apache hive traduz então essas queries em jobs de map-reduce ou de spark, dependendo da engine de processamento configurada. O hive é composto por 3 serviços principais:

- **Hive metastore**: Armazena metadados referentes a tabelas e dados para serem utilizados por motores de processamento em lote como map-reduce, presto e spark engine na execução de queries. Por debaixo dos panos o [hive metastore](https://www.ibm.com/docs/en/watsonx/watsonxdata/1.0.x?topic=components-hive-metastore-overview) utiliza um banco de dados relacional para persistir os dados, nesse caso um postgres.

- **Hive server**: Servidor responsável por responder a de queries utilizando-se de um motor de processamento e dados do hive metastore.

O apache hive é usado então para abstrair dados armazenados no HDFS em tabelas hive, a serem consumidas por processos sistẽmicos do tipo batch, ou por análise exploratória por meio do de queries HQL.

### III) Hue

O Hue é um client com interface gráfica onde é possível visualizar o sistema de pastas e arquivos do HDFS, databases e tabelas no Hive Metastore e executar ações sobre essas entidades.

### IV) Apache Spark

O Apache spark é uma engine de processamento de dados em memória distribuída. Pode ser usada para processamento de dados em batch e streaming e é altamente escalável. Pode estar em modo standalone ou tendo o Yarn como resource manager. O spark é composto por 3 serviços principais:

- **Spark Master**: Responsável por gerenciar a execução de jobs no cluster spark.
- **Spark Worker**: Responsável por executar os jobs de processamento de dados no cluster spark.
- **Spark History Server**: Serviço que armazena dados referentes a execução de jobs no cluster spark.

### V) Apache Airflow

O Apache Airflow atua como orquestador de pipelines de dados batch. Nele é possível schedular jobs e definir relações de dependência entre esses. Os jobs são definidos em DAGs (Directed Acyclic Graphs) e são compostos por tarefas. Essas tarefas utilizam operadores específicos para execução de determinadas tarefas. É possível interagir com diferentes sistemas de armazenamento de dados, como HDFS, S3, ADLS, executar jobs de processamento de dados em spark, hive, entre outros. Também é possível realizar a transferência de arquivos usando protocolos como FTP, SFTP, entre outros.

### Observação sobre serviços descritos acima

Os serviços que compõe as camadas `batch` e `fast`, são usados para interação com aplicações desenvolvidas aqui na camada `app`.
Essas tecnologias são amplamente usadas em ecossistemas de plataformas de dados. Também são open-source e possuem serviços análogos e totalmente gerenciados, na forma de **PaaS**, nos mais diversos provedores de cloud.

- O **Apache Kafka** por exemplo, tem o **Amazon MSK**, **Confluent Cloud**, **Azure Event Hubs** e **Google Cloud Pub/Sub**.
- O **Hadoop HDFS** pode ser substituído por **Amazon S3**, **Azure ADLS** e **Google Cloud Storage**. 
- O **Apache Spark** pode ser substituído por um spark gerenciado dna plataforma **Databricks** ou por outros recursos que usam por debaixo dos panos o Spark, tais como **Synapse Analytics**, **Google Dataproc**, entre outros.





## 6. Aspectos técnicos desse trabalho

Nessa seção estão apresentado alguns aspectos técnicos na implementação do sistema proposto em um ambiente local. Primeiramente, são apresentados os aspectos técnicos relacionados a  escolha do da ferramenta **docker** como base na construção desse trabalho e as formas de orquestração desses containers que são utilizadas aqui.

Em seguida, será apresentada a estrutura desse projeto, explorando as pastas e arquivos que compõem o repositório **dm_v3_chain_explorer**.

## 6.1. Dockerização dos serviços

Conforme mencionado em seções anteriores, o docker foi usado amplamente na implementação desse tabalho. O seu uso pode ser embasado de acordo com 2 propósitos.

- A construção de imagens que encapsulem jobs da camada de aplicação, bem como toda stack de software necessária para executá-los torna a aplicação portável, possibilitando que:
  - Outros entusiastas do ramo possam reproduzir o sistema em sua máquina local, usando também o docker.
  - As aplicações sejam futuramente portadas para ambientes em cloud que executam containers. Algo bem adequado em um cenário produtivo utilizando-se de serviços gerenciados de orquestração de containers. Todo provedor de cloud tem um serviço de orquestração de containers, como **ECS**, **EKS**, **AKS** e **GKE**.

- A facilidade do uso de serviços como o Kafka, hadoop, Spark e toda stack de serviço definida nas camadas `batch`, `fast` e de `operações` em containers. Essa escolha também trás alguns benefícios tais como:
  - O uso de containers abstrai a complexidade de instalação dessas ferramentas em máquina local, dado, a complexidade de muitas delas e também a quantidade de dependências e número de serviços que compõem a stack, algo que facilmente pode virar um pesadelo em ambiente local.

  - Containers são ambientes isolados que comunicam-se em rede. Apesar de compartilharem a mesma máquina física e o mesmo kernel, cada container tem seu próprio ambiente de execução. Portanto podem atuar de forma análoga a clusters, onde cada container representa um nó de um cluster. Assim é possível simular clusters de Kafka, Hadoop, Spark, entre outros, em ambiente local para testes e desenvolvimento.

  - A definição de imagens e stack de serviços a serem orquestradas é suficiente para que se possa replicar o ambiente em qualquer máquina que tenha o docker instalado e os recursos de hardware necessários.

  - Tecnologias aqui deployadas em containers, tais como spark, hadoop, kafka e outros fornecem um conhecimento mais aprofundado sobre essas tecnologias, devendo-se configurar e orquestrar esses serviços manualmente e entender sobre **volume mounts**, **networking** e outras configurações específicas dos recursos que são abstraídas em serviços gerenciados em cloud.

  - Os serviços aqui deployados em containers e open source podem ser facilmente substituídos por serviços análogos em cloud, caso haja a necessidade de se construir um ambiente produtivo robusto, seguro e eficiente.
  
## 6.2. Orquestração de serviços em containers

Conforme mencionado, todos os serviços do sistema **dm_v3_chain_explorer** rodarão instanciados localmente em containers a partir de imagens docker. Então se faz necessário o uso de uma ferramenta de orquestração de execução desses containers. O docker tem 2 ferramentas para esse propósito: **docker-compose** e **docker-swarm**.

### 6.2.1. Docker-compose

O docker-compose é uma ferramenta que permite definir e executar aplicações multi-container. Com ele é possível definir os serviços que compõem a aplicação em um arquivo `docker-compose.yml` e então instanciar esses serviços em containers. O docker-compose é uma ferramenta de orquestração de containers para **ambiente local executando em um único nó**.

É a ferramenta ideal para ambiente de desenvolvimento local e testes, onde é possível definir a stack de serviços que compõem a aplicação e instanciá-los em containers. Com o docker-compose é possível definir volumes, redes, variáveis de ambiente, entre outros, para cada serviço.

### 6.2.2. Docker-swarm

O docker-swarm é uma ferramenta de orquestração de containers para **ambientes distribuídos**. Com ele é possível definir e instanciar serviços em múltiplos nós. O docker-swarm pode ser usado como ferramenta de orquestração de containers para ambientes de produção, onde é necessário alta disponibilidade, escalabilidade e tolerância a falhas. Existem outras ferramentas de orquestração de containers, como **Kubernetes**, **Mesos** e outras, que são mais robustas e possuem mais recursos que o docker-swarm. Porém, o docker-swarm é uma ferramenta simples e fácil de usar para orquestração de containers em ambientes distribuídos e default no docker.

### 6.2.3. Docker-Compose e Docker Swarm nesse trabalho

O docker compose foi usado para orquestrar diferentes serviços nesse trabalho em seu desenvolvimento. Por exemplo, as aplicações em python, desenvolvidas e encapsuladas em imagens python, e que capturam os dados da rede Ethereum, foram orquestradas em containers usando o docker-compose juntamente com o Kafka, Redis, Scylla, entre outros.

Por outro lado, a medida que o número de serviços aumentou, a necessidade de mais recursos de hardware para execução desses serviços também cresceu. Então, o docker-swarm foi usado para orquestrar esses serviços em múltiplos nós, simulando um ambiente distribuído. Da forma como foi feito, foi possível simular um ambiente de produção, onde os serviços estão distribuídos em múltiplos nós e orquestrados por um gerenciador de containers.

#### Considerações

1. Apesar de inúmeras ferramentas em cloud terem seus benefícios, o uso restrito delas pode trazer dependência de fornecedores de cloud. A construção de um sistema que usa tecnologias open source, e que de toda forma pode ser portado para cloud, é uma forma de se manter independente desses fornecedores.

2. Existem outras possibilidades de deploy e orquestração de containers que poderiam ter sido utilizadas aqui. Por exemplo o uso de clusters Kubernetes para orquestração de containers e o uso de operadores para deploy de serviços como Kafka, Spark, Hadoop, entre outros, baseados em Helm Charts. O uso de Kubernetes traria benefícios como autoescalonamento, alta disponibilidade, entre outros. Porém, a escolha do Docker Swarm foi feita por simplicidade e configuração em ambiente local, bastando o docker instalado.

## 6.3. Estrutura do projeto

### 4.3.1. Pasta Docker

Na pasta `/docker`, localizada na raiz do repositório **dm_v3_chain_explorer** estão definidas as imagens docker que compõem esse trabalho. Elas estão organizadas de acordo com suas respectivas camadas, sendo essas `app_layer`, `fast_layer`, `batch_layer`, e `ops_layer`.

- As imagens definidas em **app_layer** são as aplicações desenvolvidas em python para capturar os dados e interagircom redes EVM, como a rede Ethereum.

- As imagens definidas nos diretórios **fast_layer**, **batch_layer** e **ops_layer** se justificam por 2 motivos:

  1. Imagens construídas uma no topo da outra, com configurações adicionais, como é o caso do Hadoop, Hive e Spark. vale dar o crédito que as imagens definidas para o Hadoop, Hive e Spark foram **fortemente baseadas nos repositórios Big Data Europe** para o [Hadoop](https://github.com/big-data-europe/docker-hadoop) e o [Hive](https://github.com/big-data-europe/docker-hive).


  2. São imagens construídas no topo de serviços pré-definidos, porém com configurações adicionais necessárias para execução desse sistema. É o caso do **Scylla** e do **Postgres** que adicionam **scripts sql/cql** a serem executados no entrypoint da imagem e que criam databases/keyspaces, users e tabelas. Ou do Kafka Connect que adiciona plugins para conexão com diferentes sistemas no topo da imagem base do Kafka Connect da **Confluent**.

```bash
docker
  ├── app_layer
  │   ├── onchain-actors
  │   ├── offchain-monitors
  │   ├── offchain-stream-txs
  │   ├── spark-streaming-jobs
  │   └── onchain-watchers
  ├── batch_layer
  │   ├── hadoop
  │   │   ├── base
  │   │   ├── namenode
  │   │   ├── datanode
  │   │   ├── resourcemanager
  │   │   ├──  nodemanager
  │   │   └── historyserver
  │   ├── hive
  │   │   ├── base
  │   │   ├── metastore
  │   │   └── server
  │   ├── postgres
  │   ├── spark
  │   │   ├── hadoop-base
  │   │   ├── hive-base
  │   │   ├── spark-base
  │   │   ├── spark-master
  │   │   └── spark-worker
  │   └── hue
  ├── fast_layer
  │   ├── kafka-connect
  │   ├── scylladb
  └── ops_layer
      └── prometheus
```

Com esses arquivos é possível fazer o build das imagens que compõem esse trabalho.

### 6.3.2. Pasta Services

Na pasta `/services`, localizada na raiz do repositório **dm_v3_chain_explorer** estão definidos os serviços que compõem esse trabalho. Esses serviços estão organizados de acordo com a camada a que pertencem, sendo essas camadas `fast`, `batch`, `app` e `ops`.

```bash
services
  ├── app_layer
  │   ├── cluster_compose.yml
  │   └── cluster_swarm.yml
  ├── batch_layer
  │   ├── cluster_compose.yml
  │   └── cluster_swarm.yml
  ├── fast_layer
  │   ├── cluster_compose.yml
  │   └── cluster_swarm.yml
  └── ops_layer
      ├── cluster_compose.yml
      └── cluster_swarm.yml
```

Os serviços estão definidos em arquivos `docker-compose.yml` e `docker-swarm.yml` para orquestração de containers em ambiente local e distribuído, respectivamente. E na pasta `/services` estão organizados de acordo com a camada a que pertencem.

### 6.3.3. Arquivo Makefile

Para simplificar esse processo de execução de comandos docker, de build e deploy de serviços, publicação de imagens, entre outros, foi definido um arquivo chamado [Makefile](https://www.gnu.org/software/make/manual/make.html) na raíz desse projeto. O Makefile é um componente central, para que comandos sejam reproduzidos de maneira simples. no arquivo `/Makefile`, na base do repositório **dm_v3_chain_explorer** é possivel visualizar os comandos definidos.

<img src="./img/Makefile.png" alt="Makefile" width="90%"/>

**Observação**: Essa ferramenta vem previamante instalada em sistemas operacionais Linux. Caso não possua o make instalado e tenha dificuldades para instalá-lo, uma opção não tão custosa é abrir o arquivo e executar os comandos docker manualmente.

### 6.3.4. Pasta Scripts

Na pasta `/scripts`, localizada na raiz do repositório **dm_v3_chain_explorer** estão definidos scripts shell úteis para automação de tarefas mais complexas.

- **0_create_dm_v3_structure.sh**: Cria a pasta `docker/app_layer` e clona os repositórios da aplicação para dentro dele.
- **1_create_swarm_networks.sh**: Cria as redes docker para orquestração de containers em ambiente distribuído.
- **2_start_prod_cluster.sh**: Cria cluster Swarm para posterior deploy de serviços em ambiente distribuído.

A chamada para execução desses scripts se dá também pelo uso de comandos definidos no `Makefile`.

### 6.3.5. Pasta Mnt

Na pasta `/mnt`, localizada na raiz do repositório **dm_v3_chain_explorer** estão definidos volumes que são montados em containers para persistência de dados localmente.

### 6.3.6. Estrutura geral do projeto

```bash
dm_v3_chain_explorer
  ├── docker
  │   ├── app_layer
  │   ├── batch_layer
  │   ├── fast_layer
  │   └── ops_layer
  ├── img
  ├── mnt
  ├── scripts
  ├── services
  │   ├── app_layer
  │   ├── batch_layer
  │   ├── fast_layer
  │   └── ops_layer
  ├── Makefile
  └── README.md
```


## 7. Reprodução do sistema `dm_v3_chain_explorer`

Nessa seção está definido o passo-a-passo para reprodução do sistema **dm_v3_chain_explorer** em ambiente local, um dos requisitos deste trabalho. A reprodutibilidade é importante pelos seguintes motivos:

- A reprodução do trabalho permite que os avaliadores executem o mesmo e compreendam como ele funciona.

- O **dm_v3_chain_explorer** é um sistema complexo, tendo diversos serviços interagindo com aplicações para que sua finalidade seja alcançada. Provêr um passo-a-passo para o leitor possa reproduzi-lo dá a este a oportunidade de entendê-lo em análise e síntese.

O passo a passo indica como clonar repositórios, configurar ambiente e deployar os serviços em um ambiente local, single-node com **Docker Compose**.

Ao final é apresentada uma maneira de deployar este em um ambiente distribuído, multi-node usando o **Docker Swarm**.

**Observação**: Um fator crucial e de maior dificuldade para reprodução desse sistema é a **necessidade de API Keys** para interagir com a rede blockchain por meio de um provedor Node-as-a-Service.

## 7.1. Requisitos

Para reprodução em ambiente local, é necessário que os seguintes requisitos sejam satisfeitos.

### 7.1.1. Requisitos de hardware

É recomendado possuir uma máquina com:

- 16 GB memória RAM de no mínimo
- Processador com 4 núcleos.

Pelo número de containers que serão instanciados, é necessário que a máquina tenha recursos de hardware suficientes para execução desses containers.

### 7.1.2. Sistema Operacional

Esse sistema foi desenvolvido e testado em ambiente Linux em Ubuntu 22.04. Portanto, é recomendado que para reprodução desse o sistema operacional seja Linux.

### 7.1.3. Docker Instalado

Para reproduzir esse sistema em ambiente local, é necessário ter o docker instalado e configurado. Para verificar se o docker está instalado e configurado adequadamente, execute os comandos abaixo.

```bash
docker version
```

A saída esperada é algo como:

<img src="./img/reproduction/1_docker_installed.png" alt="Makefile" width="80%"/>

Caso não esteja instalado, siga as instruções de instalação no [site oficial do docker](https://docs.docker.com/engine/install/).

### 7.1.4.  Docker Compose e Docker Swarm instalados

As ferramentas de orquestração de containers **Docker Compose** e **Docker Swarm** são necessárias para deployar os serviços em ambiente local e distribuído, respectivamente. Contudo elas são instaladas junto com o docker. Para verificar se estão instaladas adequadamente, execute os comandos abaixo.

```bash
docker-compose version
```

A saída esperada é algo como:

<img src="./img/reproduction/2_docker_compose_installed.png" alt="docker-compose-version" width="80%"/>

```bash
docker swarm --help
```

A saída esperada é algo como:

<img src="./img/reproduction/3_swarm_installed.png" alt="docker-swarm-version" width="80%"/>

### 7.1.5.  Git instalado

O git é necessário para que o leitor possa clonar os repositórios que compõem esse trabalho. Para verificar se o git está instalado, execute o comando abaixo.

```bash
git --version
```

<img src="./img/reproduction/4_git_installed.png" alt="docker-swarm-version" width="80%"/>

### 7.2. Setup do ambiente local

Esse trabalho é composto por multiplos repositórios, conforme mencionado. O 1º passo para reprodução desse sistema é clonar o repositório base, definido como **dm_v3_chain_explorer**.

Para isso, execute o comando abaixo e em seguida navegue para o diretório do projeto e em seguida navegue para a pasta usando o terminal.

```bash
git clone git@github.com:marcoaureliomenezes/dm_v3_chain_explorer.git
cd dm_v3_chain_explorer
```

Esse repositorio é a base do sistema. Porém, é preciso também clonar os demais repositórios da camada de aplicação. Conforme dito na seção 6, um script chamado `0_create_dm_v3_structure.sh` foi criado para esse propósito e pode ser executado a partir do seguinte comando make:

```bash
make create_dm_v3_explorer_structure
```

O comando acima clonará todos os repositórios de aplicação necessários para dentro da pasta `/docker`.

### 7.2.1.  Pull e Build das imagens docker

No docker é possível construir imagens a partir de um arquivo `Dockerfile` e depois fazer o build delas. Ou ainda, é possível fazer o pull de imagens já construídas e disponíveis no docker hub entre outros repositórios de imagens.

Para esse sistema diversas imagens foram construídas, devido a necessidade de customização. Geralmente essas imagens são construídas no topo de imagens base, que são imagens oficiais ou de terceiros, e disponíveis no docker hub. Para construir as imagens desse sistema, execute o comando abaixo.

```bash
make build
```

<img src="./img/reproduction/5_docker_images_tagged.png" alt="imagens docker tagueadas" width="90%"/>

### Observação sobre o build a partir do Makefile

Todas as imagens construídas ou personalizadas possuem tags apontando para o repositório **marcoaureliomenezes** no docker hub.

É possível o leitor reapontar essa configuração para seu próprio repositório do DockerHub caso queira deployar imagens semelhantes.

**Para execução local desse sistema usando o docker-compose** não é necessário que as imagens estejam construídas ou disponíveis no docker hub. Caso não estejam, é necessário construí-las localmente. Por esse motivo, todos os arquivos de docker-compose, aqui chamados de **cluster_compose** estão configurados para fazer build das imagens localmente.

Porém, **para executar o sistema em um ambiente distribuído usando o Docker Swarm**, é necessário que as imagens estejam disponíveis em um repositório de imagens, como o Docker Hub. Isso porque diferentes nós do cluster precisam acessar as mesmas imagens para instanciar os serviços. Por esse motivo, é necessário que as imagens sejam construídas e publicadas no Docker Hub. Para publicar as imagens no Docker Hub, execute o comando abaixo.

```bash
make publish
```

## 7.3. Reprodução do sistema usando o Docker Compose

Caso o leitor queira deployar o sistema em ambiente local, single-node, usando o **docker-compose**, os passos a seguir devem ser seguidos.

## 7.3.1. Observação sobre execução usando Docker Compose

A execução de todas as camadas de serviço em uma máquina local pode ser pesada, esgotando-se os recursos de hardware disponíveis. Por tanto que além dos requisitos citados, o leitor execute as camadas de serviço de forma separada, conforme descrito abaixo.

- Camada de operações;
- Camada Fast e camada App;
- Camada Batch.

Para que fosse possível executar todos os serviços em conjunto, foi então necessária a construção de um **cluster Swarm distribuído**.

## 7.3.2.  Deploy de serviços da camada de Operações

Conforme visto na seção de arquitetura técnica, a **camada ops** é composta por serviços que realizam telemetria dos recursos de infraestrutura do **dm_v3_chain_explorer**. Ela é composta dos seguintes serviços:

- **Prometheus**: Serviço de monitoramento de telemetria.
- **Grafana**: Serviço de visualização de telemetria.
- **Node Exporter**: Agente para coletar dados de telemetria do nó em específico.
- **Cadvisor**: Agente para coletar dados de telemetria do docker.

Para realizar o deploy da **camada ops**, execute o comando abaixo.

```bash
make deploy_dev_ops && make watch_dev_ops
```

<img src="./img/reproduction/6_lake_ops_compose_ps.png" alt="Containers de operações" width="100%"/>

**Observação**: Após execução do comando, o terminal ficará monitorando o estado dos containers. Para sair dessa tela, pressione `Ctrl + C`. Os serviços continuarão rodando em background.

Quando os serviços estiverem saudáveis, seguintes endpoints passam a estar disponíveis para a **camada ops**:

| Serviço        | Endpoint              |
|----------------|-----------------------|
| Prometheus     | http://localhost:9090 |
| Grafana        | http://localhost:3000 |

A interface do Grafana pode ser acessada no navegador, digitando o endereço `http://localhost:3000`. O usuário e senha padrão são `admin` e `admin`, respectivamente.

### Adicionando dashboards ao Grafana

- Para adicionar o dashboard do Node Exporter e do docker, clique em `+` no lado esquerdo da tela, e depois em `Import`. No campo `Grafana.com Dashboard` digite o número `1860` e clique em `Load`. Em seguida, selecione o Prometheus como fonte de dados e clique em `Import`.

- Para adicionar o dashboard referente ao Docker, repita o processo usando o ID `193` no campo `Grafana.com Dashboard`.

<img src="./img/reproduction/7_grafana_node_exporter.png" alt="grafana_node_exporter" width="80%"/>

<img src="./img/reproduction/8_grafana_container.png" alt="grafana_container" width="80%"/>


## 7.3.4.  Deploy de serviços da camada Fast

A **camada fast** é composta pelos seguintes serviços, deployados em containers:

- **1 Apache Zookeeper**: Utilizado por cluster de brokers Kafka para gestão de metadados e sincronização entre eles.
- **1 Broker Apache Kafka**: Utilizado como pub-sub para comunicação entre Jobs e como e backbone de dados, provendo esses dados em tempo real para fluxos downstream.
- **1 Confluent Schema Registry**: Serviço para registro de schemas de dados, usado para garantir compatibilidade entre diferentes versões de dados.
- **1 Confluent Kafka Connect**: Usado para integração do Kafka com o HDFS e com o S3.
- **1 Confluent Control Center**: Serviço com interface gráfica para visualização de tópicos, kafka clusters, consumer groups, schemas, clusters e jobs de kafka-connect.
- **1 Database ScyllaDB**: Banco de dados NoSQL persistente usado para controle de consumo de API Keys em processos de captura dos dados.
- **1 Redis**: Banco de dados em memória usado para garantir que uma API Key não será utilizada ao mesmo tempo por 2 processos.
- **1 Spark Master e 1 Spark Worker**: Cluster Spark utilizado em job streaming que processa logs e registra consumo de API Key.

Para deploy da camada `fast`, execute o comando abaixo.

```bash
make deploy_dev_fast && make watch_dev_fast
```

<img src="./img/reproduction/9_lake_fast_compose_ps.png" alt="layer_batch_docker_compose_ps" width="90%"/>

**Observação**: Após execução do comando, o terminal ficará monitorando o estado dos containers. Para sair dessa tela, pressione `Ctrl + C`. Os serviços continuarão rodando em background.

Quando os serviços estiverem saudáveis, seguintes endpoints passam a estar disponíveis para a **camada fast**:

| Serviço        | Endpoint              |
|----------------|-----------------------|
| Control Center | http://localhost:9021 |
| Redis Commander| http://localhost:8081 |
| Spark Master   | http://localhost:8080 |

Os conectores do Kafka Connect podem ser gerenciados tanto pelo Control Center quanto por interações com sua API Rest disponibilizada. O mesmo vale para o Schema Registry. No Makefile estão definidos comandos para interação com esses serviços.

## 7.3.5.  Deploy de serviços da camada de Aplicações

A **camada de aplicação** é composta pelos seguintes serviços:

- **mined-blocks-crawler**: Aplicação que captura dados de blocos minerados e os ids de transações contidas nesse bloco os envia para tópicos do Kafka.
- **mined-txs-crawler**: Aplicação que usa hash_ids de transações para obter dados dessas transações, classifica-las de acordo com o tipo e enviar para se respectivo tópico do Kafka.
- **txs-input-decoder**: Aplicação que busca converter
- **api_keys_log_processor**: Job Spark Streaming que consume tópico de logs e registra consumo de API Keys em tabela do ScyllaDB.

Para deploy da **camada app**, execute o comando abaixo.

```bash
make deploy_dev_app && make watch_dev_app
```

<img src="./img/reproduction/10_lake_app_compose_ps.png" alt="docker-compose ps em cluster compose app" width="90%"/>

Com os serviços da camada **fast** e **app** deployados irá começar o fluxo de captura e ingestão de dados. Na seção seguinte será mostrado como visualizar esse fluxo em funcionamento.

## 7.4. Visualização do processo de captura e ingestão de dados

Com os serviços das camadas **fast** e **app** deployados é possível visualizar o sistema de captura e ingestão em funcionamento. Seguem abaixo os passos para visualização do processo de captura e ingestão de dados.

### 7.4.1. Job Spark Streaming `api_keys_log_processor`

Na camada de aplicação foi deployado o job de spark streaming `api_keys_log_processor`. Nas seções anteriores foi detalhado o funcionamento desse Job. Em resumo ele consome o tópico de logs e monitora o consumo de API Keys, registrando esse consumo em uma tabela no ScyllaDB.

Para visualizar o Job executando na Spark UI, acesse o endereço `http://localhost:8080` no navegador.

 monitora o consumo de API Keys e atualiza a tabela no ScyllaDB. Para visualizar o Job executando na Spark UI, acesse o endereço `http://localhost:8080` no navegador.

<img src="./img/reproduction/11_spark_streaming_app.png" alt="Job Spark Streaming Monitoramento de consumode API Keys" width="90%"/>

### 7.4.2. Visualização de consumo diário de API Keys no ScyllaDB

O Job de Spark Streaming `api_keys_log_processor` monitora o consumo de API Keys e atualiza a tabela `api_keys_node_providers` no ScyllaDB. Para visualizar o consumo diário de API Keys, execute o comando abaixo.

```bash
docker exec -it scylladb cqlsh -e "select * from operations.api_keys_node_providers"
# OU
make query_api_keys_consumption_table
```

<img src="./img/reproduction/12_api_key_consumption_table.png" alt="Consumo diário de API Keys" width="90%"/>

Será possivel acompanhar o consumo de API Keys em tempo real, conforme os dados são capturados e processados pelo Job de Spark Streaming `api_keys_log_processor`.

### 7.4.3. Semáforo para consumo de API Keys no Redis

Abaixo é mostrado o controle de consumo de API Keys no Redis.

Conforme mencionado, para manter a integridade dos dados, é necessário que uma API Key não seja consumida ao mesmo tempo por 2 processos. Para isso, um semáforo é implementado no Redis utilizando uma estrutura chamada hash, estrutura no formato:

- Chave é a API Key.
- O valor é um timestamp da última vez que foi consumida e o nome do job que a consumiu.

Na figura abaixo é possível visualizar esse semáforo de API Keys no Redis.

<img src="./img/reproduction/13_redis_acting_as_a_semaphore.png" alt="Semáforo de API Keys usando o redis" width="90%"/>

**Observação**: Foi criado um job específico para coletar com frequência de 500 ms as API Keys registradas no redis e juntá-las em uma só chave, chamada **api_keys_semaphore**. Assim o leitor pode visualizar melhor o semáforo de API Keys em funcionamento, conforme a figura acima.

### 7.4.4. Dados sendo exibidos pelo Kafka Control Center

Com o mecanismo de captura de dados e de gerenciamento de API Keys para compartilhamento entre jobs funcionando os dados passam a fluir pelos tópicos do Kafka.

Abaixo é possível ver uma amostra das mensagens sendo enviadas para o tópico `ethereum-blocks` no Kafka. Essas mensagens são capturadas pela aplicação `block-clock` e enviadas para o Kafka.

<img src="./img/reproduction/14_data_flowing_through_topic.png" alt="Streaming de dados em tópico Kafka" width="90%"/>
<hr>

## 7.3.7.  Deploy de serviços da camada Batch


## 7.3.6. Deploy de conectores Kafka Connect

Os conectores Kafka Connect são responsáveis por integrar o Kafka com outros sistemas, como o HDFS e o S3. Para deploy dos conectores, execute o comando abaixo.

```bash
make deploy_dev_connectors
```

<img src="./img/reproduction/15_lake_connectors_compose_ps.png" alt="Conectores Kafka Connect" width="90%"/>



## 7.4. Reprodução do sistema usando o Docker Swarm

Comando para iniciação de cluster

Comandos para deploy de serviços



## 8. Conclusão

Toda parte teórica e prática planejada para esse trabalho foi implementada. Demonstrações do workflow de captura descritos nesse documento serão feitas na apresentação, de forma que os avaliadores possam entender melhor o sistema **dm_v3_chain_explorer**, aqui proposto.

Assim os avaliadores podem colocar suas dúvidas sobre o trabalho e também dúvidas técnicas sobre as tecnologias usadas, de maneira a avaliar da melhor forma o conhecimento desse autor nos campos relacionados a engenharia de dados. É dificil mensurar o quanto conhecimento em tecnologia está contido nesse trabalho. A construção de uma plataforma de dados para captura e ingestão de dados.

## 9. Melhorias futuras

Esse trabalho, após ser submetido continuará a ser desenvolvido, visto as possibilidades que ele apresenta, mesmo que seja apenas no campo de estudos e desenvolvimento de hard skills.
Seguem abaixo listadas algumas dessa melhorias

### 9.1. Aplicações downstream para consumo dos dados

Está descrito nesse documento, somente o fluxo de captura, ingestão e algum processamento para obter dados em tempo real de uma blockchain do tipo EVM. Na apresentação serão demonstradas algumas aplicações downstream que evoluídas podem ter diversas aplicabilidades.

### 9.2. Melhoria em aplicações do repositório onchain-watchers

Como será apresentado, esse repositório tem aplicações que usam dados das transações ingestadas para obter dados de estado provenientes de contratos inteligentes. Para isso uma arquitetura voltada a eventos precisa ser implementada. Por exemplo, quando uma transação de swap de token WETH no protocolo DEFI Uniswap é feito, um evento é disparado para que dados da piscina de liquidez e preço dos tokens sejam ingestados no sistema.

### 9.3. Troca do uso de provedores Blockchain Node-as-a-Service

Conforme visto nesse trabalho o uso de provedores node-as-a-service tais como Infura e Alchemy limitam as requisições http para request dos dados. Então, a troca desses por nós proprietários é um passo importante para evolução do sistema, ao lidar com redes mais escalaveis do tipo EVM.

### 9.4. Evolução dos serviços de um ambiente local para ambiente produtivo

Conforme visto ao longo desse trabalho, todos os serviços usados, com exceção das aplicações construídas propriamente dita para esse sistema, tem versões totalmente gerenciadas em provedores de Cloud. O Kafka por exemplo pode ser substituído pelo Event Hub ou Amazon MSK ou Clonfluent Cloud. O data lake hadoop pode ser substituído por data lakes em recursos do tipo object storages, tais como S3 ou Azure ADLS. O Hive e o Spark podem ser substituídos pelo Delta Lake + Spark do Databricks. E assim por diante.
Os containers de aplicação podem ser migrados para executarem em recursos tais com EKS da AWS ou o AKS da Azure.

Essas são algumas das evoluções enumeradas no roadmap desse sistema.
