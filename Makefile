DOCKER_NETWORK = docker-hadoop_default
ENV_FILE = hadoop.env
current_branch = 1.0.0

create_dm_v3_chain_explorer_structure:
	sh scripts/0_create_dm_v3_chain_explorer_structure.sh

build:
	# docker build -t marcoaureliomenezes/dm-hadoop-base:$(current_branch) ./docker/batch_layer/hadoop/base
	# docker build -t marcoaureliomenezes/dm-hadoop-namenode:$(current_branch) ./docker/batch_layer/hadoop/namenode
	# docker build -t marcoaureliomenezes/dm-hadoop-datanode:$(current_branch) ./docker/batch_layer/hadoop/datanode
	# docker build -t marcoaureliomenezes/dm-hadoop-resourcemanager:$(current_branch) ./docker/batch_layer/hadoop/resourcemanager
	# docker build -t marcoaureliomenezes/dm-hadoop-nodemanager:$(current_branch) ./docker/batch_layer/hadoop/nodemanager
	# docker build -t marcoaureliomenezes/dm-hadoop-historyserver:$(current_branch) ./docker/batch_layer/hadoop/historyserver
	# docker build -t marcoaureliomenezes/dm-postgres:$(current_branch) ./docker/batch_layer/postgres
	# docker build -t marcoaureliomenezes/dm-hive-base:$(current_branch) ./docker/batch_layer/hive/base
	# docker build -t marcoaureliomenezes/dm-hive-metastore:$(current_branch) ./docker/batch_layer/hive/metastore
	# docker build -t marcoaureliomenezes/dm-hive-server:$(current_branch) ./docker/batch_layer/hive/server
	# docker build -t marcoaureliomenezes/dm-hue-webui:$(current_branch) ./docker/batch_layer/hue
	# docker build -t marcoaureliomenezes/dm-spark-hadoop-base:$(current_branch) ./docker/batch_layer/spark/hadoop-base
	# docker build -t marcoaureliomenezes/dm-spark-hive-base:$(current_branch) ./docker/batch_layer/spark/hive-base
	# docker build -t marcoaureliomenezes/dm-spark-base:$(current_branch) ./docker/batch_layer/spark/spark-base
	# docker build -t marcoaureliomenezes/dm-spark-master:$(current_branch) ./docker/batch_layer/spark/spark-master
	# docker build -t marcoaureliomenezes/dm-spark-worker:$(current_branch) ./docker/batch_layer/spark/spark-worker
	# docker build -t marcoaureliomenezes/dm-apache-airflow:$(current_branch) ./docker/batch_layer/airflow/
	# docker build -t marcoaureliomenezes/dm-scylladb:$(current_branch) ./docker/fast_layer/scylladb
	# docker build -t marcoaureliomenezes/dm-kafka-connect:$(current_branch) ./docker/fast_layer/kafka-connect
	# docker build -t marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	# docker build -t marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs
	# docker build -t marcoaureliomenezes/dm-prometheus:$(current_branch) ./docker/ops_layer/prometheus

#########################	COMANDOS DE PUBLICAÇÃO DE IMAGENS   ###########################

publish:
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
	# docker push dm_data_lake/scylladb:$(current_branch)
	# docker push dm_data_lake/kafka-connect:$(current_branch)
	# docker push marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch)


#################    DEPLOY CONTAINERS SINGLE NODE    ##########################

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
#################    STOP CONTAINERS SINGLE NODE    ###########################

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

#################    WATCH CONTAINERS SINGLE NODE    #############################

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
########################    SWARM CLUSTER    #####################################

# COMANDO DE INICIALIZAÇÃO DO CLUSTER SWARM
start_prod_cluster:
	sh scripts/start_prod_cluster.sh

#################    DEPLOY CONTAINERS CLUSTER SWARM     #########################

deploy_prod_fast:
	docker stack deploy -c services/fast/cluster_swarm.yml layer_fast

deploy_prod_app:
	docker stack deploy -c services/app/cluster_swarm.yml layer_app

deploy_prod_batch:
	docker stack deploy -c services/batch/cluster_swarm.yml layer_batch

deploy_prod_ops:
	docker stack deploy -c services/ops/cluster_swarm.yml layer_ops


#################    STOP CONTAINERS CLUSTER SWARM    ############################

stop_prod_fast:
	docker stack rm layer_fast

stop_prod_app:
	docker stack rm layer_app

stop_prod_batch:
	docker stack rm layer_batch

stop_prod_ops:
	docker stack rm layer_ops

#################    WATCH CONTAINERS CLUSTER SWARM    ###########################

watch_prod_services:
	watch docker service ls


#############################    FIM    ##########################################