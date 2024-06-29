# dm_v3_chain_explorer System

Neste repositório se encontra a implementação e documentação de um case de estudo desenvolvido.

Estão aqui implementadas estratégias e rotinas de extração, ingestão, processamento, armazenamento e uso de dados com origem em protocolos P2P do tipo blockchain, assim como definições imagens docker e arquivos yml com serviços utilizados. Esse trabalho foi desenvolvido para o case do programa Data Master.

## Sumário

- 1. Objetivo do case;
  - 1.1. Objetivos de negócio;
  - 1.2. Introdução;
    - 1.2.1.  Redes Blockchain, Públicas e privadas;
    - 1.2.2.  Contratos inteligentes;
    - 1.2.3. Oportunidades em blockchains públicas compatíveis com EVM;
    - 1.2.4.  Possibilidade em blockchains privadas;
  - 1.3. Objetivos técnicos;
  - 1.4. Observação sobre o tema escolhido;

- 2. Explicação sobre o case desenvolvido;
  - 2.1. Captura de dados;
  - 2.2. Restrições de API keys;
  - 2.3. Mecanismo para captura de dados;
    - 2.3.1.  Captura dos dados do bloco mais recente;
    - 2.3.2.  Captura de dados de transações;
    - 2.3.3.  Separação de transações por finalidade;
    - 2.3.4.  Decode do campo input contido em transações;
  - 2.4. Sistema Pub / Sub;

- 3. Arquitetura do case;
  - 3.1. Arquitetura de solução;
  - 3.2. Arquitetura Técnica;
    - 3.2.1.  Camada Fast;
    - 3.2.2.  Camada Batch;
    - 3.2.3.  Camada de aplicação;
      - Observação sobre aplicações e repositórios desse trabalho;
    - 3.2.4. Camada de operação;
    - 3.2.5.  Segurança da plataforma;

- 4. Aspectos técnicos desse trabalho;
  - 4.1. Docker;
  - 4.2. Orquestração de containers Docker;
    - Por que usar além do docker-compose também o docker Swarm?
- 5. Reprodução da arquitetura e do case;
  - 5.1. Considerações;
  - 5.2. Pré-requisitos;
    - 5.2.1.  Requisitos de hardware;
    - 5.2.2.  Docker;
    - 5.2.3.  Docker Compose e Docker Swarm;
  - 5.3. Automação de comandos e Makefile;
  - 5.4. Passo-a-passo para reprodução do sistema;
    - 5.4.1.  Clonagem do repositório base;
    - 5.4.2.  Pull e Build das imagens docker;
    - 5.4.3.  Inicialização de ambiente de Desenvolvimento;
      - 1. Deploy de serviços da camada Fast;
      - 2. Deploy de serviços da camada de Batch;
        - 2.1. Hadoop Namenode;
      - 3. Deploy de serviços da camada de Aplicação;
      - 4. Deploy de serviços da camada de operações;

- 6. Conclusão;
- 7. Melhorias futuras;
  - 7.1.1.  Aplicações downstream para consumo dos dados;
  - 7.1.2.  Melhoria em aplicações do repositório onchain-watchers;
  - 7.1.3.  Troca do uso de provedores Blockchain Node-as-a-Service;
  - 7.1.4.  Evolução dos serviços de um ambiente local para ambiente produtivo;

## 1. Objetivo do Case

O objetivo final desse trabalho é sua submissão para o programa Data Master, e posterior apresentação do mesmo à banca de Data Experts em engenharia de dados do Santander Brasil. Nessa apresentação serão avaliados conceitos e técnicas de engenharia de dados, entre outros campos, aplicados na construção prática deste sistema entitulado **dm_v3_chain_explorer**.

Para alcançar tal objetivo final e, dados os requisitos do case, especificados pela organização do programa, para a construção desse sistema foram definidos objetivos específicos, categorizados em objetivos de negócio e objetivos técnicos.

### 1.1. Objetivos de negócio

A solução apresentada aqui tem como objetivo de negócio criar uma plataforma na qual dados, provenientes de transações com origem em redes blockchain em tempo real possam alimentar aplicações de monitoramento, analytics e bots para interação nessas mesmas redes.

Eis um objetivo de negócio que é construído tendo como base uma tecnologia nova e complexa.

### 1.2. Introdução

Para alcançar o objetivo de negócio mencionado é necessário um sistema capaz de capturar, ingestar e armazenar dados com origem em redes P2P do tipo blockchain.
Se faz necessária então uma introdução ao tema. Assim o leitor tem a oportunidade de compreender o quão engenhosa é essa tecnologia e as possibilidades e oportunidades que a exploração dela trazem.

O sistema aqui desenvolvido possibilita a extração de dados dessas redes P2P, ao capturar,ingestar e armazená-los. Após esse processo os dados estão prontos para consumo de aplicações downstream. Essas aplicações downstream vão desde Analytics, auditoria e segurança e observabilidade da rede, e aplicativos que se relacionam a contratos inteligentes, até bots que interagem com esses mesmos contratos.

Quando se fala em blockchain vale distinguir que o termo blockchain, tecnicamente, pode ser usado pra se referir a:

- **Estrutura de dados blockchain** que armazena blocos de forma encadeada. Cada bloco contém um conjunto de transações efetuadas por usuários da rede, entre outros metadados. Um desses metadados é o hash do bloco atual e o hash do bloco anterior, o que garante a integridade da cadeia de blocos. Isso porque se algum dado é alterado em um bloco anterior, o hash desse bloco passa a ser diferente do hash anterior no bloco seguinte.

- **Rede blockchain**, de topologia Peer-to-Peer onde nós validam transações e mineram novos blocos, estes construídos em uma estrutura de dados blockchain mencionada acima. Todos os nós da rede possuem uma cópia dessa estrutura de dados e são sincronizados entre si. Assim, novos blocos minerados (contendo transações), após consenso, são adicionados ao blockchain permanentemente a rede. E todos nós para que a rede possa validar a integridade das transações contidas em todos os blocos.

#### Observação

Não é requisito no case do Data Master usar blockchain. Porém, dada a natureza tecnológica dessa fonte de dados, bem como seus possíveis casos de uso, a escolha dessa temática para o trabalho se justifica. Com muita simplicidade, uma blockchain nada mais é do que uma forma de usuários transacionarem entre si através de uma rede sem a necessidade de um intermediário. A própria rede garante sua segurança. E essas transações podem ser troca de tokens nativos da rede (criados a cada bloco minerado) ou interação com contratos inteligentes.

### 1.2.1. Redes Blockchain, Públicas e privadas

Blockchains públicas são redes P2P que armazenam uma estrutura de dados do tipo blockchain. Por serem públicas permitem que qualquer nó possa fazer parte na rede, aumentando a decentralização da mesma. Assim qualquer pessoa, desde que com requisitos de hardware, software e rede satisfeitos, podem fazer parte dessa rede. Ja redes de blockchain privadas existe uma restrição de quem pode se tornar um membro da rede.

Em sistemas decentralizados, por natureza distribuídos, não é possível ter tudo. Assim como, para sistemas distribuídos existe o [Teorema CAP](https://www.ibm.com/br-pt/topics/cap-theorem), para sistemas decentralizados, do tipo blockchain existe, de forma análoga, o [Trilema do blockchain](https://www.coinbase.com/pt-br/learn/crypto-glossary/what-is-the-blockchain-trilemma), que diz entre 3 características, decentralização, segurança e escalabilidade, somente é possível alcançar plenamente 2 dessas, sendo necessário sacrificar a terceira. Entre as redes de blockchain se destacam:

- **Bitcoin**: 1ª blockchain construída, por natureza pública e na qual seu token nativo, o BTC tem alto valor de mercado. Até recentemente seu principal uso era o de investidores que usam o token BTC como reserva de valor.
- **Ethereum**: 1ª blockchain, também por natureza pública, com possiblidade deploy e interação com contratos inteligentes altamente decentralizada, porém para manter essa decentralização, é lenta (baixo número de transações por bloco) e frequencia na publicação de blocos é baixa;
- **Tron, Cardano Avalanche, Binance Smart Chain, Fantom**: Blockchains públicas de Layer 1 que se utilizam também da EVM por ser open source. menos decentralizadas que a ethereum porém mais rápidas;
- **Polygon, arbitrum, Optimist, Base**: Blockchains de Layer 2 que rodam no topo da ethereum, são EVM (executam a Etherem Virtual Machine);
- **Blockchains construídas a partir da plataforma Hyperledger**: Blockchains privadas usadas por empresas para uso interno. São redes permissionadas, ou seja, somente membros autorizados podem fazer parte da rede;
- **Solana e outras**: Blockchains Layer 1 que tem sua própria virtual machine, diferente da EVM.

Cada uma delas usa uma estratégia e previlegia 2 características específicas para atender ao seus objetivos.

Muitos protocolos de rede blockchain privados, como é o caso do Hyperledger Besu usado no DREX, são compatíveis com a EVM. Assim como as layers 2, esses podem se beneficiar de todo SDK de desenvolvimento de contratos e até da segurança fornecida pela rede ethereum, altamente decentralizada e segura, por meio da publicação de provas de consistência nessas redes.

### 1.2.2. Contratos inteligentes

Nesse trabalho o interesse é em protocolos que possuem contratos inteligentes. Contratos inteligentes são desenvolvidos através de uma linguagem de programação e toda uma pilha de software para que funcionem como uma máquina de estados. Para uma melhor compreensão sobre smart contracts [esse material pode ser um bom começo](https://www.coinbase.com/pt-br/learn/crypto-basics/what-is-a-smart-contract).

Para se calcular o estado da rede (lembre-se que essa funciona em baixo nível como blocos sendo minerados com certa frequência e estes contendo transações) as redes blockchain fazem o uso de uma virtual machine.

Para a rede Ethereum foi criada uma virtual machine chamada máquina virtual open source chamada EVM – [Ethereum Virtual Machine](https://blog.bitso.com/pt-br/tecnologia/ethereum-virtual-machine)


### 1.2.3. Oportunidades em blockchains públicas compatíveis com EVM

Conforme dito acima, existem inúmeras redes blockchain públicas onde circula uma quantidade significativa de capital. Em algumas delas existe um ecossistema diverso de aplicações construídas a partir de contratos inteligentes. Essas redes são usadas para, desde a transferência de tokens entre endereços, até a interação com contratos inteligentes, por meio da execução de funções deste, para aplicações dos mais diversos fins.

1. Em [DeFi Llama Chains](https://defillama.com/chains) é possível ver o quanto capital está alocado em cada uma dessas redes. A rede Ethereum, por exemplo, é a rede com maior capital preso em smart contracts do protocolo (TVL). É inegável que as instituções financeiras tenham interesse em oferecer como produto a venda desses tokens, tais como BTC e ETH. Alguns bancos já o fazem. Mas qual seria o 1º passo para uma instituição financeira, altamente regulada, oferecer um produto como esse? Uma das etapas seria claramente a criação de mecanismos de segurança, para, por exemplo, monitorar e assegurar que pessoas sancionadas ou envolvidas em lavagem de dinheiro não transacionem livremente usando endereços ligados a instituição.

2. Nessas redes blockchains, além de transações de transferência de token nativo, são executadas funções em contratos inteligentes. Esses contratos são programas deployados em um bloco da rede com endereço próprio. Após deployados esses contratos armazenam estado e passam a estar disponíveis para interação. Isso permite que aplicações descentralizadas (dApps) sejam criadas dentro do protocolo. Dessa forma, é possível criar, por exemplo, aplicações financeiras descentralizadas (DeFi) que permitem empréstimos, trocas de tokens, entre outras funcionalidades. Em [DeFi Llama](https://defillama.com/) é possível ver uma lista de aplicações DeFi e o volume de capital retido em cada uma delas. 

Ao capturar as transações em tempo real, transações do tipo interação com contratos inteligentes, é possível monitorar qual usuário está chamando qual função de qual contrato inteligente da rede e com quais parâmetros. Não caberia nesse documento mensurar a vasta gama de oportunidades que se abrem ao capturar esses dados, armazena-los e torna-los disponíveis para fluxos downstream.

### 1.2.4. Possibilidade em blockchains privadas

O DREX, projeto do banco central do Brasil, é um exemplo de uso de blockchain privada. Além de se criar o real digital, o DREX oferece as mesmas funcionalidades de uma rede blockchain pública, como a execução de contratos inteligentes.

Ele funcionará com base em uma rede blockchain compativel com a EVM. [Nessa reportagem da Exame](https://exame.com/future-of-money/banco-central-quer-integracao-do-drex-com-ethereum-e-outros-blockchains-tradicionais/) é possível se obter mais informações sobre. Fica clara a utilidade de um sistema como o **dm_v3_chain_explorer**, podendo esse ser usado para monitorar e auditar transações e interações com contratos inteligentes nessa rede.

###  1.3. Objetivos técnicos

Para alcançar os objetivos de negócio propostos é preciso implementar um sistema capaz de capturar, ingestar, processar, persistir e utilizar dados da origem mencionada. Para isso, foram definidos os seguintes objetivos técnicos:

- Criar sistema de captura de dados brutos de redes de blockchain públicas.
- Criar um sistema de captura de dados de estado em contratos inteligentes.
- Criar um sistema de captura agnóstico à rede de blockchain, porém restrito a redes do tipo EVM (Ethereum Virtual Machine).
- Criar uma arquitetura de solução que permita a ingestão lambda.
- Minimizar latência e números de requisições, e maximizar a disponibilidade do sistema.
- Criar um ambiente reproduzível e escalável com serviços necessários à execução de papeis necessários ao sistema.
- Armazenar e consumir dados pertinentes a operação e análises em bancos analíticos e transacionais.
- Implementar ferramentas monitorar o sistema (dados de infraestrutura, logs, etc).

Para alcançar tais objetivos, como será explorado mais adiante, um grande desafio apareceu e é talvez o ponto mais complexo desse trabalho. A maneira de capturar esses dados, através da interação com provedores de nós blockchain-as-a-service e API keys.

### 1.4. Observação sobre o tema escolhido

Dado que a tecnologia blockchain não é assunto trivial e também não é um requisito especificado no case, apesar da introdução feita acima, no corpo principal desse trabalho evitou-se detalhar o funcionamento de contratos inteligentes e aplicações DeFi mais que o necessário. Porém, é entendido pelo autor desse trabalho que, apesar de não ser um requisito especificado no case, inúmeros conceitos aqui abordados exploram com profundidade campos como:

- Estruturas de dados complexas (o próprio blockchain);
- Arquiteturas de sistemas distribuídos e descentralizados;
- Conceitos relacionados a finanças.

Portanto, a escolha desse tema para case é uma oportunidade de aprendizado e de aplicação de conhecimentos de engenharia de dados, arquitetura de sistemas, segurança da informação, entre outros.

## 2. Explicação sobre o case desenvolvido

Foi escolhido para esse trabalho o uso da rede Ethereum como fonte de dados. Isso é justificado na introdução e objetivos de negócio acima, sendo os fatores de peso:

- Capital retido na rede Ethreum;
- Compatibilidade de aplicações entre diferentes blockchains baseadas na EVM.

Sempre é dito que dados de blockchain são públicos. O que não significa que estejam disponíveis facilmente. Para capturar dados dessas fontes é preciso ter acesso um nó da rede, para capturar dados e submeter transações. E é possível se ter um nó próprio ou usar um nó de terceiros.

Devido aos requisitos de hardware, software e rede necessários para deploy de um nó, seja on-premises ou em cloud, foi escolhido nesse trabalho o uso de **provedores de Node-as-a-Service ou NaaS**. Esses provedores, como modelo de negócio, fornecem API keys para interação com os nós. Porém, limitam a quantidade de requisições, de acordo com planos estabelacidos (gratuito, premium, etc.) que variam o preço e o limite de requisições diárias ou por segundo permitidas.

O objetivo do sistema aqui proposto é capturar e ingestar os dados brutos de transações da rede Ethereum com a menor latência possível. Foi optado pelo uso de provedores NaaS. Com o número de requisições limitadas, restrição desses provedores, é preciso criar um mecanismo sofisticado para captura. O mesmo mecanismo será útil, caso um dia um nó próprio seja deployado. Operaçoes de rede são custosas e, portanto, é preciso minimizar o número de requisições e manter um controle delas.

Por ser encarado como um desafio técnico, reduzir o custo para captura desses dados a zero virtualmente, satisfazendo os objetivos mencionados se mostra um caminho interessante.

### 2.1. Captura de dados

Conforme mencionado, é preciso acesso a um nó de uma rede especifica para obter os dados da mesma. Certamente, esses dados podem ser obtidos de maneira indireta - alguém captura os dados e coloca em um database para serem usados. Contudo aqui se busca a forma direta, de maneira a satisfazer o requisito de minimização da latência para captura e ingestão dos dados.
Dado que o acesso ao nó esteja resolvido, ainda sim é preciso interagir com ele para se obter os dados. Existem SDKs para diferentes linguagens de programação, para interação com esses nós. Aqui nesse trabalho, para interação com os nós foram usadas as seguintes ferramentas:

- [Biblioteca Web3.py](https://web3py.readthedocs.io/en/stable/) para interação com a rede e captura de dados de blocos e transações;

- [Framework brownie](https://eth-brownie.readthedocs.io/en/stable/python-package.html,) construída no topo da biblitoeca Web3.py para interação com contratos inteligentes chamada.

Dado que ambos os pontos estejam satisfeitos, é possível fazer a ingestão de dados em tempo real, certo? Não exatamente.

### 2.2. Restrições de API keys

As requisições em nós disponibilizados por um provedor de NaaS são limitadas de 2 formas. O provedor infura por exemplo, fornece uma API key em seu plano gratuito com as seguintes restrições:

- Máximo de **10 requests por segundo**;
- Máximo de  **100.000 requests por dia**.

Na rede Ethereum, um bloco tem tamanho em bytes limitado e é minerado a cada 8 segundos. Cada bloco contém em média 250 transações. Isso resulta em:

- **2,7 milhões de transações por dia**;
- **31 transações por segundo**.

Aqui está dados o desafio. Como será visto a diante, o mecanismo **para se capturar n transações de um bloco recém-minerado** exige que sejam feitas em média **n + 8 requisições**. Usando o plano gratuito, obviamente é necessário o uso de inúmeras API Keys. Porém o gerenciamento de uso dessas, de maneira a manter a disponibilidade e confiabilidade do sistema traz a necessidade de um mecanismo engenhoso. Aqui então ela se apresenta.

Para capturar dados de blocos e transações da rede em tempo real usando o pacote python `web3.py`, foram desenvolvidas rotinas que representam Jobs, com determinadas funcionalidades, como será visto nos tópicos adiante. Esses jobs comunicam entre si por meio de um sistema Pub-Sub, que é um sistema de mensagens assíncrono, onde um publisher publica mensagens em um tópico e um subscriber consome essas mensagens.

### 2.3. Mecanismo para captura de dados

Nos subtópicos dessa sessão está detalhado o mecanismo para ingestão em tempo real dos dados de uma rede blockchain compatível com EVM. Eles se baseam em 2 funções específicas do pacote `web3.py`:

- **get_block(block_number)**: Retorna um dicionário com os metadados do bloco e uma lista de hash_ids de transações pertencentes àquele bloco. Pode receber o parâmetro `latest` para capturar o bloco mais recente.

- **get_transaction(tx_hash)**: Retorna um dicionário com os dados da transação referente ao hash_id passado como parâmetro.

De forma simplória, é possivel com esses métodos capturar todas as transações da rede. Porém, deve ser considerado como os jobs que utilizam essas funções trabalharão em conjunto para capturar os dados de maneira eficiente. Faz necessário também considerar a limitação de requisições impostas pelos provedores de NaaS.

### 2.3.1.  Captura dos dados do bloco mais recente

O job **block_clock** está implementado para que, a cada período de tempo, parametrizado e por padrão 1 segundo, execute o método `get_latest_block()`, que obtém dados o último bloco adicionado à cadeia. Entre os dados obtidos estão o número do bloco, outros metadados e uma lista de hash_id de transações pertencentes àquele bloco. Se obtendo o número do bloco mais recente é possível identificar novos blocos minerados, ao se perceber que o número foi incrementado. E então disparar um evento com os dados do bloco.

Esse job então publica na plataforma do tipo Pub-Sub na forma de mensagem:

- Metadados do bloco minerado em um tópico chamado **mined.blocks.metadata**;
- Cada `hash_id` da lista de transações do bloco bloco monerado no tópico  **mined.txs.hash.ids**.

A cada execução do método `get_latest_block()` uma requisição é feita consumindo a API key. Porém, com a frequencia de `1 req/segundo`, tem-se **86400 requisições por dia**. Para satisfazer tal número de requisições 1 chave é o suficiente.

### 2.3.2. Captura de dados de transações

O job **raw_tx_ingestor** tem por finalidade, usando o método `get_transaction(tx_hash_id)` obter os dados de uma transação. Para alcançar seu objetivo ele se subscreve no tópico **mined.txs.hash.ids** de forma a consumir os `hash_ids` enviados pelo job **block_clock**.

Conforme os hash_ids são consumidos, o job **raw_tx_ingestor** executa o método `get_transaction(tx_hash_id)` para obter os dados daquela transação. Esses dados são então publicados em um tópico chamado **raw_data_txs**.

Nesse job concentra-se o esforço em número de requisições.Como mencionado, o número de transações diárias na rede Ethereum ultrapassam em muito os limites de uma API Key para 1 plano gratuito. Logo é necessário que esse job seja escalado. Mas escalado de que forma?

Para segurança do sistema, essas API Keys não podem estar cravas no código, pois a mesma rotina será usada por diferentes instâncias do job. A 1ª solução que vem a mente é passar a API Key por parâmetro. Porém, isso não é seguro. Caso uma API Key tenha seus recursos esgotados, o job não poderá mais consumir dados e não haverá uma maneira de se manter o controle sobre isso. Para garantir os requisitos de **latência e disponibilidade do sistema**, é preciso um mecanismo mais sofisticado para que esses jobs compartilhem as API Keys de forma inteligente.

**Redução da Latência**: Cada API Key é limitada por requests por segundo. Então, se há multipals instâncias do job **raw_tx_ingestor** consumindo dados, é preciso que em dado instante de tempo t, cada API Key seja usada por somente 1 job. Dessa forma, a taxa de requisições por segundo é maximizada.

**Máxima disponibilidade**: Para garantir a disponibilidade do sistema, é preciso manter o controle de requisições nas API Keys para que somente em último caso as requisições sejam esgotadas.
Caso o número de requisições diárias seja atingido o job deve trocar de API Key. É interessante também que as instâncias do job troquem de API Keys de tempos em tempos, para que todas as API Keys sejam usadas de maneira equitativa. Para isso, é preciso um mecanismo de controle de uso das API Keys.

### 2.3.2. Mecanismo de compartilhamento de chaves entre réplicas do job

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

### 2.3.3.  Separação de transações por finalidade

O job **tx_classifier** tem por finalidade classificar as transações brutas recebidas, a partir de uma subscrição no tópico **raw.data.txs** e publicá-las seus respectivos tópicos:

- **mined.tx.1.native_token_transfer**: transação de troca de token nativo entre 2 endereços de usuários;
- **mined.tx.2.contract_deployment**: transação realizando o deploy de um contrato inteligente;
- **mined.tx.3.contract_interaction**: Interação de um endereço de usuário com um contrato inteligente.

Após classificados em tópicos, cada tipo de transação pode alimentar aplicações downstream, cada uma com sua especificidade.

### 2.3.4.  Decode do campo input contido em transações

As transações publicadas no tópico **mined.tx.3.contract_interaction** correspondem a interação com contratos inteligentes. Isso se dá por meio de chamada de funções do mesmo passando-see parâmetros. Por exemplo, para se trocar Ethereum por outros tokens na rede Uniswap, é necessário chamar a função `swapExactETHForTokens` passando os parâmetros necessários.

Nesses tipos de transaçãoo campo `input` é onde se encontra a informação de qual função do contrato foi executada e quais parâmetros foram passados para ela. Porém, esses dados vem encodados. É necessário um mecanismo para decodificar esses dados e torná-los legíveis. Para isso, foi criado o job **tx_input_decoder**.

Este tem por finalidade fazer o decode do campo input. Para que isso seja possível, é necessário que o contrato inteligente tenha uma ABI (Application Binary Interface) disponível. A ABI é um JSON que contém a assinatura de todas as funções do contrato. Com a ABI é possível decodificar o campo input e identificar qual função foi chamada e quais parâmetros foram passados.

Se o objetivo é decodificar o campo input de transações de interação com contratos inteligentes, para todo contrato inteligente, é preciso que a ABI de todos os contratos esteja disponível. Para isso, será criada na próxima versão o job **contract_abi_ingestor**.

### 2.4. Sistema Pub / Sub para comunicação entre Jobs

Para viabilizar a rotina descrita acima, como mencionado, é necessário que os jobs comuniquem-se entre si. É então necessário um sistema do tipo Fila ou **Publisher-Subscriber**.

Uma fila, tal como **RabbitMQ**, por exemplo, satisfaria os requisitos de comunicação entre os Jobs. Porém, é necessário também que os dados publicados, como mencionado, em tópicos, sejam persistidos e possam ser consumidos por por multiplos atores subscritos nesses tópicos.

Essa plataforma Pub-Sub será o back-bone do **dm_v3_chain_explorer**. Logo, esta deve satisfazer requisitos de escalabilidade, resiliencia e robustez. O **Apache Kafka** se mostrou a solução ideal para essa finalidade.

O dm_v3_chain_explorer é desenhado para trabalhar de modo agnóstico a rede blockchain, desde que esta use a EVM. Existem uma infinidade de redes desse tipo sendo todas elas mais rápidas que a Ethereum em número de transações por bloco e frequência de blocos minerados.

Então, se esse sistema é desenhado para ser usado com diferentes blockchains, inclusive ao mesmo tempo, ele deve estar preparado para escalar. E como ponto de falha mais crítico backbone da aplicação, é a plataforma Pub-Sub deve estar pronta para suportar workloads de bigdata. Por isso o Apache Kafka foi escolhido.

## 3. Arquitetura do case

Nesse tópico está detalhada a arquitetura de solução e técnica do dm_v3_chain_explorer. Foi explorado acima alguns atores no mecanismo que realiza a captura e ingestão do dados. Porém é necessário entender com clareza como estes componentes comunicam-se entre si.
3.1. Arquitetura de solução
O desenho abaixo ilustra como a solução para captura e ingestão de dados da Ethereum, e em tempo real funciona.

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

### 1.3 Inicialização e gerenciamento de cluster Swarm

#### Table of urls

| Camada |     Serviço      |  URL Exposta Compose   |      URL Exposta Swarm      |
|--------|------------------|------------------------------------------------------|
|  Fast  | KAFKA UI         | http://localhost:9021  | http://192.168.15.101:9021  |
|  Fast  | SPARK UI         | http://localhost:18080 | http://192.168.15.101:18080 |
|  Fast  | REDIS UI         | http://localhost:18081 | http://192.168.15.101:18081 |
|  Fast  | VISUALIZER SWARM | http://localhost:28080 | http://192.168.15.101:28080 |
|  Batch | NAMENODE UI      | http://localhost:8080  | http://192.168.15.101:8080  |
|  Batch | HUE UI           | http://localhost:32762 | http://192.168.15.101:32762 |
|  Batch | AIRFLOW UI       | http://localhost:8080  | http://192.168.15.101:8080  |
|  Ops   | GRAFANA UI       | http://localhost:3000 | http://192.168.15.101:13000  |
|  Ops   | PROMETHEUS UI    | http://localhost:9090  | http://192.168.15.101:9090  |


1. **Inicialização do cluster Swarm**: Dado que os nós do cluster estão disponíveis, então o cluster pode ser inicializado com o comando:

```bash
make start_swarm_cluster
```

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
