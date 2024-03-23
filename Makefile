DOCKER_NETWORK = docker-hadoop_default
ENV_FILE = hadoop.env
current_branch = 1.0.0

build:
	docker build -t dm_data_lake/onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	docker build -t dm_data_lake/spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs


	docker build -t dm_data_lake/scylladb:$(current_branch) ./docker/fast_layer/scylladb
	docker build -t dm_data_lake/kafka-connect:$(current_branch) ./docker/fast_layer/kafka-connect

create_topics:
	docker-compose -f services/cluster_dev_app.yml start topics_creator

deploy_dev_fast:
	docker-compose -f services/cluster_dev_fast.yml up -d
	docker-compose -f services/cluster_dev_app.yml up -d

deploy_prod_fast:
	docker stack deploy -c services/cluster_prod_fast.yml layer_fast
	docker stack deploy -c services/cluster_prod_app.yml layer_app

deploy_prod_batch:
	docker stack deploy -c services/cluster_prod_batch.yml layer_batch
	
deploy_dev_batch:
	docker-compose -f services/cluster_dev_batch.yml up -d


stop_dev_fast:
	docker-compose -f services/cluster_dev_fast.yml down
	docker-compose -f services/cluster_dev_app.yml down
	#docker stop $(docker ps -a -q) > /dev/null

stop_dev_batch:
	docker-compose -f services/cluster_dev_batch.yml down

watch_dev_services:
	watch docker-compose -f services/cluster_dev_fast.yml ps

watch_prod_services:
	watch docker service ls

delete_volumes:
	# docker volume prune
	docker volume rm $(docker volume ls -q) >> /dev/null

delete_images:
	# docker image prune
	docker rmi $(docker images -q) >> /dev/null