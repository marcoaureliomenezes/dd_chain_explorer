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


dev_start:

	docker-compose -f services/cluster_dev_fast.yml up -d
	docker-compose -f services/cluster_dev_app.yml up -d
	# docker-compose -f services/cluster_dev_batch.yml up -d

dev_stop:
	docker-compose -f services/cluster_dev_fast.yml down
	docker-compose -f services/cluster_dev_app.yml down
	docker-compose -f services/cluster_dev_batch.yml down
	#docker stop $(docker ps -a -q) > /dev/null



dev_watch:
	watch docker-compose -f services/cluster_dev_fast.yml ps
