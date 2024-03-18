# Data Master Services

Nesse repositório estão contidas as definições todos os serviços utilizados no case, a ser apresentado em 2024.

## 1 - Ferramentas utilizadas

### 1.1 Docker

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



Tecnologia de ar