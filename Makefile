DOCKER_NETWORK = docker-hadoop_default
ENV_FILE = hadoop.env
current_branch = 1.0.0

create_dm_v3_chain_explorer_structure:
	sh scripts/0_create_dm_v3_chain_explorer_structure.sh

build:

	# HADOOP CLUSTER RELATED BUILD
	# docker build -t marcoaureliomenezes/dm-hadoop-base:$(current_branch) ./docker/batch_layer/hadoop/base
	# docker build -t marcoaureliomenezes/dm-hadoop-namenode:$(current_branch) ./docker/batch_layer/hadoop/namenode
	# docker build -t marcoaureliomenezes/dm-hadoop-datanode:$(current_branch) ./docker/batch_layer/hadoop/datanode
	# docker build -t marcoaureliomenezes/dm-hadoop-resourcemanager:$(current_branch) ./docker/batch_layer/hadoop/resourcemanager
	# docker build -t marcoaureliomenezes/dm-hadoop-nodemanager:$(current_branch) ./docker/batch_layer/hadoop/nodemanager
	# docker build -t marcoaureliomenezes/dm-hadoop-historyserver:$(current_branch) ./docker/batch_layer/hadoop/historyserver

	# # HIVE RELATED BUILD
	# docker build -t marcoaureliomenezes/dm-postgres:$(current_branch) ./docker/batch_layer/postgres
	# docker build -t marcoaureliomenezes/dm-hive-base:$(current_branch) ./docker/batch_layer/hive/base
	# docker build -t marcoaureliomenezes/dm-hive-metastore:$(current_branch) ./docker/batch_layer/hive/metastore
	# docker build -t marcoaureliomenezes/dm-hive-server:$(current_branch) ./docker/batch_layer/hive/server
	# docker build -t marcoaureliomenezes/dm-hue-webui:$(current_branch) ./docker/batch_layer/hue
	
	# # SPARK CLUSTER RELATED BUILD
	# docker build -t marcoaureliomenezes/dm-spark-hadoop-base:$(current_branch) ./docker/batch_layer/spark/hadoop-base
	# docker build -t marcoaureliomenezes/dm-spark-hive-base:$(current_branch) ./docker/batch_layer/spark/hive-base
	# docker build -t marcoaureliomenezes/dm-spark-base:$(current_branch) ./docker/batch_layer/spark/spark-base
	# docker build -t marcoaureliomenezes/dm-spark-master:$(current_branch) ./docker/batch_layer/spark/spark-master
	# docker build -t marcoaureliomenezes/dm-spark-worker:$(current_branch) ./docker/batch_layer/spark/spark-worker

	# AIRFLOW RELATED BUILD
	# docker build -t marcoaureliomenezes/dm-apache-airflow:$(current_branch) ./docker/batch_layer/airflow/

	# BUILD FAST LAYER IMAGES
	# docker build -t marcoaureliomenezes/dm-scylladb:$(current_branch) ./docker/fast_layer/scylladb
	# docker build -t marcoaureliomenezes/dm-kafka-connect:$(current_branch) ./docker/fast_layer/kafka-connect

	# BUILD APP LAYER IMAGES
	# docker build -t marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	docker build -t marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs

#########################	COMANDOS DE PUBLICAÇÃO DE IMAGENS   ###########################

publish:
	# docker push marcoaureliomenezes/dm-scylladb:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-namenode:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-datanode:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-resourcemanager:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-nodemanager:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-historyserver:$(current_branch)
	# # docker push marcoaureliomenezes/dm-postgres:$(current_branch)
	# # docker push marcoaureliomenezes/dm-hive-metastore:$(current_branch)
	# # docker push marcoaureliomenezes/dm-hive-server:$(current_branch)
	# # docker push marcoaureliomenezes/dm-hue-webui:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-master:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-worker:$(current_branch)
	# # docker push marcoaureliomenezes/dm-apache-airflow:$(current_branch)
	# # docker push dm_data_lake/scylladb:$(current_branch)
	# # docker push dm_data_lake/kafka-connect:$(current_branch)
	docker push marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch)
	docker push marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch)


# COMANDOS PARA DEPLOY DE CONTAINERS EM AMBIENTE DE DESENVOLVIMENTO (DOCKER COMPOSE)


deploy_dev_fast:
	docker-compose -f services/fast/cluster_compose.yml up -d --build

deploy_dev_app:
	docker-compose -f services/app/cluster_compose.yml up -d --build

deploy_dev_batch:
	docker-compose -f services/batch/cluster_compose.yml up -d

deploy_dev_ops:
	docker-compose -f services/ops/cluster_compose.yml up -d

#######################  STOP SERVICES   #######################################

stop_dev_fast:
	docker-compose -f services/fast/cluster_compose.yml down

stop_dev_batch:
	docker-compose -f services/batch/cluster_compose.yml down

stop_dev_app:
	docker-compose -f services/app/cluster_compose.yml down

stop_dev_ops:
	docker-compose -f services/ops/cluster_compose.yml down

#######################  WATCH SERVICES   ######################################

watch_dev_batch:
	watch docker-compose -f services/batch/cluster_compose.yml ps

watch_dev_fast:
	watch docker-compose -f services/fast/cluster_compose.yml ps

watch_dev_app:
	watch docker-compose -f services/app/cluster_compose.yml ps

watch_dev_ops:
	watch docker-compose -f services/ops/cluster_compose.yml ps

#########################  COMANDOS DE MONITORAMENTO    ###########################
watch_dev_batch_services:
	watch docker-compose -f services/cluster_dev_batch.yml ps


create_topics:
	docker-compose -f services/cluster_dev_app.yml start topics_creator


#########################  COMANDOS EM PRODUÇÃO   ###########################

# COMANDO DE INICIALIZAÇÃO DO CLUSTER SWARM
start_prod_cluster:
	sh scripts/start_prod_cluster.sh



# DEPLOY DE STACK DE CAMADA DE MONITORAMENTO
deploy_prod_operations:
	docker stack deploy -c operations/docker-compose.prod.yml layer_operations

# STOP DE STACK DE CAMADA OPERATIONS
stop_prod_operations:
	docker stack rm layer_operations


# DEPLOY DE STACK DE CAMADA FAST
deploy_prod_fast:
	docker stack deploy -c services/cluster_prod_fast.yml layer_fast

# STOP DE STACK DE CAMADA FAST
stop_prod_fast:
	docker stack rm layer_fast


# DEPLOY DE STACK DE CAMADA BATCH
deploy_prod_batch:
	docker stack deploy -c services/cluster_prod_batch.yml layer_fast

# STOP DE STACK DE CAMADA BATCH
stop_prod_batch:
	docker stack rm layer_fast


# DEPLOY DE STACK DE CAMADA APP
deploy_prod_app:
	docker stack deploy -c services/cluster_prod_app.yml layer_fast

# STOP DE STACK DE CAMADA APP
stop_prod_app:
	docker stack rm layer_app


# COMANDO DE MONITORAMENTO DE SERVIÇOS EM PRODUÇÃO
watch_prod_services:
	watch docker service ls

#########################	COMANDOS DE LIMPEZA   ###########################


