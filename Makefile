current_branch = 1.0.0

####################################################################################################
####################################################################################################
#####################    COMANDOS PARA CONFIGURAÇÃO DO AMBIENTE    #################################

start_cluster_swarm:
	sh scripts/1_start_cluster_swarm.sh

start_prod_cluster:
	sh scripts/1_start_cluster_swarm.sh

####################################################################################################
#################################    BUILD DE IMAGENS DOCKER    ####################################
####################################################################################################

build_customized:
	docker build -t marcoaureliomenezes/spark:$(current_branch) ./docker/customized/spark
	docker build -t marcoaureliomenezes/rosemberg:$(current_branch) ./docker/customized/jupyterlab

build_prometheus:
	# sh scripts/cp_prometheus_conf.sh
	docker build -t marcoaureliomenezes/prometheus:$(current_branch) ./docker/customized/prometheus

build_airflow:
	sh scripts/cp_airflow_dags.sh
	docker build -t marcoaureliomenezes/airflow:$(current_branch) ./docker/customized/airflow

build_apps:
	# docker build -t marcoaureliomenezes/onchain-batch-txs:$(current_branch) ./docker/app_layer/onchain-batch-txs
	# docker build -t marcoaureliomenezes/onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	docker build -t marcoaureliomenezes/spark-batch-jobs:$(current_branch) ./docker/app_layer/spark-batch-jobs
	docker build -t marcoaureliomenezes/spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs

####################################################################################################
####################################################################################################
############################	   PUSH DOCKER IMAGES TO DOCKER-HUB    ###############################

publish_customized:
	docker push marcoaureliomenezes/spark:$(current_branch)
	docker push marcoaureliomenezes/rosemberg:$(current_branch)
	docker push marcoaureliomenezes/prometheus:$(current_branch)
	docker push marcoaureliomenezes/airflow:$(current_branch)


publish_apps:
	docker push marcoaureliomenezes/onchain-batch-txs:$(current_branch)
	# docker push marcoaureliomenezes/onchain-stream-txs:$(current_branch)
	# docker push marcoaureliomenezes/spark-batch-jobs:$(current_branch)
	docker push marcoaureliomenezes/spark-streaming-jobs:$(current_branch)

####################################################################################################
####################################################################################################
###############################    DEPLOY COMPOSE SERVICES    ######################################

deploy_dev_services:
	docker compose -f services/compose/python_streaming_apps_layer.yml up -d --build
	# docker compose -f services/compose/airflow_orchestration_layer.yml up -d --build
	# docker compose -f services/compose/spark_streaming_apps_layer.yml up -d --build

deploy_test_batch:
	docker compose -f services/compose/batch_apps_layer.yml up -d --build

####################################################################################################
################################    STOP COMPOSE SERVICES    #######################################

stop_dev_all:
	docker compose -f services/compose/python_streaming_apps_layer.yml down
	# docker compose -f services/compose/airflow_orchestration_layer.yml down
	# docker compose -f services/compose/spark_streaming_apps_layer.yml down

stop_dev_batch:
	docker compose -f services/compose/batch_apps_layer.yml down

watch_dev_compose:
	watch docker compose -f services/compose/python_streaming_apps_layer.yml ps

####################################################################################################
####################################################################################################
#################################    DEPLOY SWARM STACKS    ########################################

deploy_prod_all:
	docker stack deploy -c services/swarm/observability_layer.yml layer_observability
	docker stack deploy -c services/swarm/lakehouse_layer.yml layer_lakehouse
	docker stack deploy -c services/swarm/fast_layer.yml layer_fast
	docker stack deploy -c services/swarm/processing_layer.yml layer_processing
	# docker stack deploy -c services/swarm/orchestration_layer.yml layer_orchestration

deploy_prod_observability:
	docker stack deploy -c services/swarm/observability_layer.yml layer_observability

deploy_prod_lakehouse:
	docker stack deploy -c services/swarm/lakehouse_layer.yml layer_lakehouse

deploy_prod_fast:
	docker stack deploy -c services/swarm/fast_layer.yml layer_fast

deploy_prod_processing:
	docker stack deploy -c services/swarm/processing_layer.yml layer_processing


deploy_prod_spark_apps:
	docker stack deploy -c services/swarm/spark_apps_layer.yml layer_spark_apps
####################################################################################################
##################################    STOP SWARM STACKS    #########################################


stop_prod_all:
	docker stack rm layer_observability
	docker stack rm layer_processing
	docker stack rm layer_fast
	docker stack rm layer_lakehouse
	docker stack rm layer_app
	docker stack rm layer_orchestration

stop_prod_observability:
	docker stack rm layer_observability

stop_prod_lakehouse:
	docker stack rm layer_lakehouse

stop_prod_spark_apps:
	docker stack rm layer_spark_apps

stop_prod_fast:
	docker stack rm layer_fast

stop_prod_processing:
	docker stack rm layer_processing

stop_prod_app:
	docker stack rm layer_app

####################################################################################################
###############################    WATCH SWARM SERVICES    #########################################

watch_prod_services:
	watch docker service ls

open_services_in_browser:
	@python scripts/lazy_helper.py