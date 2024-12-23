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

build_spark:
	docker build -t marcoaureliomenezes/spark:$(current_branch) ./docker/customized/spark

build_rosemberg:
	docker build -t marcoaureliomenezes/rosemberg:$(current_branch) ./docker/customized/jupyterlab

build_prometheus:
	# sh scripts/cp_prometheus_conf.sh
	docker build -t marcoaureliomenezes/prometheus:$(current_branch) ./docker/customized/prometheus

build_airflow:
	sh scripts/cp_airflow_dags.sh
	docker build -t marcoaureliomenezes/airflow:$(current_branch) ./docker/customized/airflow

build_app:
	docker build -t marcoaureliomenezes/onchain-batch-txs:$(current_branch) ./docker/app_layer/onchain-batch-txs
	# docker build -t marcoaureliomenezes/spark-batch-jobs:$(current_branch) ./docker/app_layer/spark-batch-jobs
	# docker build -t marcoaureliomenezes/onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	# docker build -t marcoaureliomenezes/spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs

####################################################################################################
####################################################################################################
############################	   PUSH DOCKER IMAGES TO DOCKER-HUB    ###############################

publish_spark:
	docker push marcoaureliomenezes/spark:$(current_branch)

publish_rosemberg:
	docker push marcoaureliomenezes/rosemberg:$(current_branch)

publish_prometheus:
	docker push marcoaureliomenezes/prometheus:$(current_branch)

publish_airflow:
	docker push marcoaureliomenezes/airflow:$(current_branch)


publish_apps:
	docker push marcoaureliomenezes/onchain-batch-txs:$(current_branch)
	docker push marcoaureliomenezes/onchain-stream-txs:$(current_branch)
	docker push marcoaureliomenezes/spark-batch-jobs:$(current_branch)
	docker push marcoaureliomenezes/spark-streaming-jobs:$(current_branch)

####################################################################################################
####################################################################################################
###############################    DEPLOY COMPOSE SERVICES    ######################################

deploy_dev_all:
	docker compose -f services/compose/observability_layer.yml up -d
	docker compose -f services/compose/processing_layer.yml up -d
	docker compose -f services/compose/fast_layer.yml up -d
	docker compose -f services/compose/lakehouse_layer.yml up -d
	# docker compose -f services/compose/orchestration_layer.yml up -d
	docker compose -f services/compose/app_layer.yml up -d

stop_dev_all:
	docker compose -f services/compose/python_app_layer.yml down
	docker compose -f services/compose/spark_app_layer.yml down
	docker compose -f services/compose/orchestration_layer.yml down
	docker compose -f services/compose/lakehouse_layer.yml down
	docker compose -f services/compose/fast_layer.yml down
	docker compose -f services/compose/processing_layer.yml down
	docker compose -f services/compose/observability_layer.yml down

####################################################################################################
####################################################################################################

deploy_dev_python:
	docker compose -f services/compose/python_app_layer.yml up -d  --build

stop_dev_python:
	docker compose -f services/compose/python_app_layer.yml down


deploy_dev_spark:
	docker compose -f services/compose/spark_app_layer.yml up -d  --build

stop_dev_python:
	docker compose -f services/compose/python_app_layer.yml down

####################################################################################################
####################################################################################################

deploy_dev_fast:
	docker compose -f services/compose/fast_layer.yml up -d

stop_dev_fast:
	docker compose -f services/compose/fast_layer.yml down

####################################################################################################
####################################################################################################

deploy_dev_processing:
	docker compose -f services/compose/processing_layer.yml up -d --build

stop_dev_processing:
	docker compose -f services/compose/processing_layer.yml down

####################################################################################################
####################################################################################################

deploy_dev_lakehouse:
	docker compose -f services/compose/lakehouse_layer.yml up -d

stop_dev_lakehouse:
	docker compose -f services/compose/lakehouse_layer.yml down

####################################################################################################
####################################################################################################

deploy_dev_ops:
	docker compose -f services/compose/observability_layer.yml up -d
	
stop_dev_orchestration:
	docker compose -f services/compose/orchestration_layer.yml down


deploy_dev_orchestration:
	docker compose -f services/compose/orchestration_layer.yml up -d --build


stop_dev_ops:
	docker compose -f services/compose/observability_layer.yml down


####################################################################################################
###############################    WATCH COMPOSE SERVICES    #######################################

watch_dev_compose:
	watch docker compose -f services/compose/fast_layer.yml ps


####################################################################################################
####################################################################################################
#################################    DEPLOY SWARM STACKS    ########################################

deploy_prod_fast:
	docker stack deploy -c services/swarm/fast_layer.yml layer_fast

deploy_prod_processing:
	docker stack deploy -c services/swarm/processing_layer.yml layer_processing

deploy_prod_lakehouse:
	docker stack deploy -c services/swarm/lakehouse_layer.yml layer_lakehouse

deploy_prod_observability:
	docker stack deploy -c services/swarm/observability_layer.yml layer_observability

deploy_prod_orchestration:
	docker stack deploy -c services/swarm/orchestration_layer.yml layer_orchestration

deploy_prod_all:
	docker stack deploy -c services/swarm/observability_layer.yml layer_observability
	docker stack deploy -c services/swarm/processing_layer.yml layer_processing
	docker stack deploy -c services/swarm/fast_layer.yml layer_fast
	docker stack deploy -c services/swarm/lakehouse_layer.yml layer_lakehouse
	#docker stack deploy -c services/swarm/orchestration_layer.yml layer_orchestration
####################################################################################################
##################################    STOP SWARM STACKS    #########################################

stop_prod_processing:
	docker stack rm layer_processing

stop_prod_fast:
	docker stack rm layer_fast

stop_prod_app:
	docker stack rm layer_app

stop_prod_lakehouse:
	docker stack rm layer_lakehouse

stop_prod_orchestration:
	docker stack rm layer_orchestration

stop_prod_observability:
	docker stack rm layer_observability

stop_prod_all:
	docker stack rm layer_observability
	docker stack rm layer_processing
	docker stack rm layer_fast
	docker stack rm layer_lakehouse
	docker stack rm layer_app
	docker stack rm layer_orchestration
####################################################################################################
###############################    WATCH SWARM SERVICES    #########################################

watch_prod_services:
	watch docker service ls

open_services_in_browser:
	@python scripts/lazy_helper.py