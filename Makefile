DOCKER_NETWORK = docker-hadoop_default
ENV_FILE = hadoop.env
current_branch = 1.0.0


##################################################################################################################################
#######################    COMANDOS DE INICIALIZAÇÃO DE AMBIENTE DE DESENVOLVIMENTO    ###########################################
create_dm_v3_chain_explorer_structure:
	sh scripts/0_create_dm_v3_chain_explorer_structure.sh


##################################################################################################################################
#######################    COMANDOS DE INICIALIZAÇÃO DE AMBIENTE DE DESENVOLVIMENTO    ###########################################
##################################################################################################################################

build_app:
	docker build -t marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	docker build -t marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs

build_fast:
	docker build -t marcoaureliomenezes/dm-scylladb:$(current_branch) ./docker/fast_layer/scylladb
	docker build -t marcoaureliomenezes/dm-kafka-connect:$(current_branch) ./docker/fast_layer/kafka-connect

build_batch:
	docker build -t marcoaureliomenezes/dm-hadoop-base:$(current_branch) ./docker/batch_layer/hadoop/base
	docker build -t marcoaureliomenezes/dm-hadoop-namenode:$(current_branch) ./docker/batch_layer/hadoop/namenode
	docker build -t marcoaureliomenezes/dm-hadoop-datanode:$(current_branch) ./docker/batch_layer/hadoop/datanode
	docker build -t marcoaureliomenezes/dm-hadoop-resourcemanager:$(current_branch) ./docker/batch_layer/hadoop/resourcemanager
	docker build -t marcoaureliomenezes/dm-hadoop-nodemanager:$(current_branch) ./docker/batch_layer/hadoop/nodemanager
	docker build -t marcoaureliomenezes/dm-hadoop-historyserver:$(current_branch) ./docker/batch_layer/hadoop/historyserver
	docker build -t marcoaureliomenezes/dm-postgres:$(current_branch) ./docker/batch_layer/postgres
	docker build -t marcoaureliomenezes/dm-hive-base:$(current_branch) ./docker/batch_layer/hive/base
	docker build -t marcoaureliomenezes/dm-hive-metastore:$(current_branch) ./docker/batch_layer/hive/metastore
	docker build -t marcoaureliomenezes/dm-hive-server:$(current_branch) ./docker/batch_layer/hive/server
	docker build -t marcoaureliomenezes/dm-hue-webui:$(current_branch) ./docker/batch_layer/hue

build_ops:
	docker build -t marcoaureliomenezes/dm-prometheus:$(current_branch) ./docker/ops_layer/prometheus

##################################################################################################################################
#########################	   COMANDOS DE PUBLICAÇÃO DE IMAGENS NO DOCKER-HUB    ##################################################

publish_apps:
	docker push marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch)
	docker push marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch)

publish_fast:
	docker push dm_data_lake/scylladb:$(current_branch)
	docker push dm_data_lake/kafka-connect:$(current_branch)

publish_batch:
	# docker push marcoaureliomenezes/dm-scylladb:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-namenode:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-datanode:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-resourcemanager:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-nodemanager:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-historyserver:$(current_branch)
	# docker push marcoaureliomenezes/dm-postgres:$(current_branch)
	# docker push marcoaureliomenezes/dm-hive-base:$(current_branch)
	# docker push marcoaureliomenezes/dm-hive-metastore:$(current_branch)
	# docker push marcoaureliomenezes/dm-hive-server:$(current_branch)
	# docker push marcoaureliomenezes/dm-hue-webui:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-master:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-worker:$(current_branch)
	# docker push marcoaureliomenezes/dm-apache-airflow:$(current_branch)

publish_ops:
	docker push marcoaureliomenezes/dm-prometheus:$(current_branch)

##################################################################################################################################
###################    COMANDOS DE DEPLOY DE CONTAINERS EM AMBIENTE DE DESENVOLVIMENTO    ########################################

deploy_dev_fast:
	docker-compose -f services/fast/cluster_compose.yml up -d --build

deploy_dev_app:
	docker-compose -f services/app/cluster_compose.yml up -d --build

deploy_dev_batch:
	docker-compose -f services/batch/cluster_compose.yml up -d --build

deploy_dev_ops:
	docker-compose -f services/ops/cluster_compose.yml up -d

deploy_dev_airflow:
	docker-compose -f services/airflow/cluster_compose.yml up -d
	
##################################################################################################################################
#########################    COMANDOS DE STOP CONTAINERS EM AMBIENTE DE DESENVOLVIMENTO    #######################################

stop_dev_fast:
	docker-compose -f services/fast/cluster_compose.yml down

stop_dev_app:
	docker-compose -f services/app/cluster_compose.yml down

stop_dev_batch:
	docker-compose -f services/batch/cluster_compose.yml down

stop_dev_ops:
	docker-compose -f services/ops/cluster_compose.yml down

stop_dev_airflow:
	docker-compose -f services/airflow/cluster_compose.yml down

##################################################################################################################################
#########################    COMANDOS DE WATCH CONTAINERS EM AMBIENTE DE DESENVOLVIMENTO    ######################################

watch_dev_fast:
	watch docker-compose -f services/fast/cluster_compose.yml ps

watch_dev_app:
	watch docker-compose -f services/app/cluster_compose.yml ps

watch_dev_batch:
	watch docker-compose -f services/batch/cluster_compose.yml ps

watch_dev_ops:
	watch docker-compose -f services/ops/cluster_compose.yml ps

watch_dev_airflow:
	watch docker-compose -f services/airflow/cluster_compose.yml ps


##################################################################################################################################
#######################    COMANDOS DE INICIALIZAÇÃO DE AMBIENTE DE PRODUÇÃO    ##################################################

# COMANDO DE INICIALIZAÇÃO DO CLUSTER SWARM
start_prod_cluster:
	sh scripts/start_prod_cluster.sh


##################################################################################################################################
#######################    COMANDOS DE DEPLOY DE CONTAINERS EM AMBIENTE DE PRODUÇÃO    ###########################################

deploy_prod_fast:
	docker stack deploy -c services/fast/cluster_swarm.yml layer_fast

deploy_prod_app:
	docker stack deploy -c services/app/cluster_swarm.yml layer_app

deploy_prod_batch:
	docker stack deploy -c services/batch/cluster_swarm.yml layer_batch

deploy_prod_ops:
	docker stack deploy -c services/ops/cluster_swarm.yml layer_ops


##################################################################################################################################
#######################    COMANDOS DE STOP DE CONTAINERS EM AMBIENTE DE PRODUÇÃO    #############################################

stop_prod_fast:
	docker stack rm layer_fast

stop_prod_app:
	docker stack rm layer_app

stop_prod_batch:
	docker stack rm layer_batch

stop_prod_ops:
	docker stack rm layer_ops


##################################################################################################################################
#######################    COMANDOS DE WATCH DE CONTAINERS EM AMBIENTE DE PRODUÇÃO    ############################################

watch_prod_services:
	watch docker service ls


query_api_keys_consumption_table:
	docker exec -it scylladb cqlsh -e "select * from operations.api_keys_node_providers;"

##################################################################################################################################