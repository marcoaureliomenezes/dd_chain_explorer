DOCKER_NETWORK = docker-hadoop_default
ENV_FILE = hadoop.env
current_branch = 1.0.0

build:

	# HADOOP CLUSTER RELATED BUILD
	docker build -t dm_data_lake/hadoop-namenode:$(current_branch) ./docker/batch_layer/hadoop/namenode
	docker build -t dm_data_lake/hadoop-datanode:$(current_branch) ./docker/batch_layer/hadoop/datanode
	docker build -t dm_data_lake/hadoop-resourcemanager:$(current_branch) ./docker/batch_layer/hadoop/resourcemanager
	docker build -t dm_data_lake/hadoop-nodemanager:$(current_branch) ./docker/batch_layer/hadoop/nodemanager
	docker build -t dm_data_lake/hadoop-historyserver:$(current_branch) ./docker/batch_layer/hadoop/historyserver

	# HIVE RELATED BUILD
	docker build -t dm_data_lake/postgres:$(current_branch) ./docker/batch_layer/postgres
	docker build -t dm_data_lake/hive-base:$(current_branch) ./docker/batch_layer/hive
	docker build -t dm_data_lake/hive-metastore:$(current_branch) ./docker/batch_layer/hive/metastore
	docker build -t dm_data_lake/hive-server:$(current_branch) ./docker/batch_layer/hive/server
	docker build -t dm_data_lake/hue-webui:$(current_branch) ./docker/batch_layer/hue
	
	# SPARK CLUSTER RELATED BUILD
	docker build -t dm_data_lake/spark-hadoop-base:$(current_branch) ./docker/batch_layer/spark/hadoop-base
	docker build -t dm_data_lake/spark-hive-base:$(current_branch) ./docker/batch_layer/spark/hive-base
	docker build -t dm_data_lake/spark-base:$(current_branch) ./docker/batch_layer/spark/spark-base
	docker build -t dm_data_lake/spark-master:$(current_branch) ./docker/batch_layer/spark/spark-master
	docker build -t dm_data_lake/spark-worker:$(current_branch) ./docker/batch_layer/spark/spark-worker

	# AIRFLOW RELATED BUILD
	docker build -t dm_data_lake/airflow:$(current_branch) ./docker/batch_layer/airflow/

	# BUILD FAST LAYER IMAGES
	# docker build -t dm_data_lake/scylladb:$(current_branch) ./docker/fast_layer/scylladb
	# docker build -t dm_data_lake/kafka-connect:$(current_branch) ./docker/fast_layer/kafka-connect

	# BUILD APP LAYER IMAGES
	# docker build -t dm_data_lake/onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	# docker build -t dm_data_lake/spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs


create_topics:
	docker-compose -f services/cluster_dev_app.yml start topics_creator

deploy_dev_fast:
	docker-compose -f services/cluster_dev_fast.yml up -d
	docker-compose -f services/cluster_dev_app.yml up -d

deploy_dev_batch:
	docker-compose -f services/cluster_dev_batch.yml up -d

stop_dev_fast:
	docker-compose -f services/cluster_dev_fast.yml down
	docker-compose -f services/cluster_dev_app.yml down
	#docker stop $(docker ps -a -q) > /dev/null

stop_dev_batch:
	docker-compose -f services/cluster_dev_batch.yml down

watch_dev_batch_services:
	watch docker-compose -f services/cluster_dev_batch.yml ps


deploy_prod_fast:
	docker stack deploy -c services/cluster_prod_fast.yml layer_fast
	docker stack deploy -c services/cluster_prod_app.yml layer_app

deploy_prod_batch:
	docker stack deploy -c services/cluster_prod_batch.yml layer_batch
	


watch_prod_services:
	watch docker service ls

delete_volumes:
	# docker volume prune
	docker volume rm $(docker volume ls -q) >> /dev/null

delete_images:
	# docker image prune
	sh scripts/delete_images.sh