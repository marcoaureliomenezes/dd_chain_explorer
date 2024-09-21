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

build_hadoop_base:
	docker build -t marcoaureliomenezes/hadoop-base:$(current_branch) ./docker/customized/hadoop/base

build_kafka_connect:
	docker build -t marcoaureliomenezes/dm-kafka-connect:$(current_branch) ./docker/customized/kafka-connect

build_prometheus:
	sh scripts/cp_prometheus_conf.sh
	docker build -t marcoaureliomenezes/dm-prometheus:$(current_branch) ./docker/customized/prometheus

build_airflow:
	sh scripts/cp_airflow_dags.sh
	docker build -t marcoaureliomenezes/dm-airflow:$(current_branch) ./docker/customized/airflow

build_images_for_swarm:
	docker build -t marcoaureliomenezes/dm-hadoop-namenode:$(current_branch) ./docker/customized/hadoop/namenode
	docker build -t marcoaureliomenezes/dm-hadoop-datanode:$(current_branch) ./docker/customized/hadoop/datanode
	docker build -t marcoaureliomenezes/dm-hive-base:$(current_branch) ./docker/customized/hive
	docker build -t marcoaureliomenezes/dm-hive-postgres:$(current_branch) ./docker/customized/postgres/
	docker build -t marcoaureliomenezes/dm-hue-webui:$(current_branch) ./docker/customized/hue

build_app:
	docker build -t marcoaureliomenezes/dm-onchain-batch-txs:$(current_branch) ./docker/app_layer/onchain-batch-txs
	# docker build -t marcoaureliomenezes/dm-spark-batch-jobs:$(current_branch) ./docker/app_layer/spark-batch-jobs
	# docker build -t marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	# docker build -t marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs

####################################################################################################
####################################################################################################
############################	   PUSH DOCKER IMAGES TO DOCKER-HUB    ###############################

publish_kafka_connect:
	docker push dm_data_lake/dm-kafka-connect:$(current_branch)

publish_prometheus:
	docker push marcoaureliomenezes/dm-prometheus:$(current_branch)

publish_airflow:
	docker push marcoaureliomenezes/dm-airflow:$(current_branch)

publish_images_for_swarm:
	# docker push marcoaureliomenezes/dm-hadoop-namenode:$(current_branch)
	# docker push marcoaureliomenezes/dm-hadoop-datanode:$(current_branch)
	# docker push marcoaureliomenezes/dm-hive-base:$(current_branch)
	# docker push marcoaureliomenezes/dm-hive-postgres:$(current_branch)
	# docker push marcoaureliomenezes/dm-hue-webui:$(current_branch)

publish_apps:
	docker push marcoaureliomenezes/dm-onchain-batch-txs:$(current_branch)
	# docker push marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-batch-jobs:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch)

####################################################################################################
####################################################################################################
###############################    DEPLOY COMPOSE SERVICES    ######################################

deploy_dev_fast:
	docker compose -f services/compose/transactional_services.yml up -d --build

deploy_dev_app:
	docker compose -f services/compose/app_services.yml up -d --build

deploy_dev_lakehouse:
	docker compose -f services/compose/lakehouse_services.yml up -d --build

deploy_dev_ops:
	docker compose -f services/compose/observability_services.yml up -d --build
	
deploy_dev_orchestration:
	docker compose -f services/compose/orchestration_services.yml up -d --build

####################################################################################################
#############################    STOP COMPOSE SERVICES    ##########################################

stop_dev_fast:
	docker compose -f services/compose/transactional_services.yml down

stop_dev_app:
	docker compose -f services/compose/app_services.yml down

stop_dev_lakehouse:
	docker compose -f services/compose/lakehouse_services.yml down

stop_dev_orchestration:
	docker compose -f services/compose/orchestration_services.yml down

stop_dev_ops:
	docker compose -f services/compose/observability_services.yml down

####################################################################################################
###############################    WATCH COMPOSE SERVICES    #######################################

watch_dev_fast:
	watch docker compose -f services/compose/transactional_services.yml ps

watch_dev_app:
	watch docker compose -f services/compose/app_services.yml ps

watch_dev_lakehouse:
	watch docker compose -f services/compose/lakehouse_services.yml ps

watch_dev_orchestration:
	docker compose -f services/compose/orchestration_services.yml ps

watch_dev_ops:
	watch docker compose -f services/compose/observability_services.yml ps

####################################################################################################
####################################################################################################
#################################    DEPLOY SWARM STACKS    ########################################

deploy_prod_fast:
	docker stack deploy -c services/transactional/swarm_fast.yml layer_fast

deploy_prod_app:
	docker stack deploy -c services/transactional/swarm_apps.yml layer_app

deploy_prod_lakehouse:
	docker stack deploy -c services/swarm/lakehouse_services.yml layer_lakehouse

deploy_prod_orchestration:
	docker stack deploy -c services/swarm/orchestration_services.yml layer_orchestration

deploy_prod_ops:
	docker stack deploy -c services/operations/swarm_monitoring.yml layer_ops

####################################################################################################
##################################    STOP SWARM STACKS    #########################################

stop_prod_fast:
	docker stack rm layer_fast

stop_prod_app:
	docker stack rm layer_app

stop_prod_lakehouse:
	docker stack rm layer_lakehouse

stop_prod_orchestration:
	docker stack rm layer_orchestration

stop_prod_ops:
	docker stack rm layer_ops

####################################################################################################
###############################    WATCH SWARM SERVICES    #########################################

watch_prod_services:
	watch docker service ls

####################################################################################################
###############################    WATCH SWARM SERVICES    #########################################
####################################################################################################
##############################    KAFKA CONNECT COMMANDS    ########################################

connect_show_connectors:
	http :8083/connector-plugins -b

####################################################################################################
################################    MANAGE HDFS LOGS SINK DEV    ###################################

deploy_sink_application_logs_hdfs_dev:
	http PUT :8083/connectors/application-logs-hdfs-sink-dev/config @connectors/hdfs-sink-dev/application-logs.json -b

status_sink_application_logs_hdfs_dev:
	http :8083/connectors/application-logs-hdfs-sink-dev/status -b

pause_sink_application_logs_hdfs_dev:
	http PUT :8083/connectors/application-logs-hdfs-sink-dev/pause -b

stop_sink_application_logs_hdfs_dev:
	http DELETE :8083/connectors/application-logs-hdfs-sink-dev -b

####################################################################################################
#############################    MANAGE HDFS BLOCKS SINK DEV    ####################################

deploy_sink_blocks_hdfs_dev:
	http PUT :8083/connectors/block-metadata-hdfs-sink-dev/config @connectors/hdfs-sink-dev/block-metadata.json -b

status_sink_blocks_hdfs_dev:
	http :8083/connectors/block-metadata-hdfs-sink-dev/status -b

pause_sink_blocks_hdfs_dev:
	http PUT :8083/connectors/block-metadata-hdfs-sink-dev/pause -b

stop_sink_blocks_hdfs_dev:
	http DELETE :8083/connectors/block-metadata-hdfs-sink-dev -b

####################################################################################################
###############################    MANAGE HDFS LOGS SINK DEV    ####################################

deploy_sink_contract_call_hdfs_dev:
	http PUT :8083/connectors/contract-call-hdfs-sink-dev/config @connectors/hdfs-sink-dev/contract-call-txs.json -b

status_sink_contract_call_hdfs_dev:
	http :8083/connectors/contract-call-hdfs-sink-dev/status -b

pause_sink_contract_call_hdfs_dev:
	http PUT :8083/connectors/contract-call-hdfs-sink-dev/pause -b

stop_sink_contract_call_hdfs_dev:
	http DELETE :8083/connectors/contract-call-hdfs-sink-dev -b

####################################################################################################
#############################    MANAGE HDFS BLOCKS SINK DEV    ####################################

deploy_sink_token_transfer_hdfs_dev:
	http PUT :8083/connectors/token-transfer-hdfs-sink-dev/config @connectors/hdfs-sink-dev/token-transfer-txs.json -b

status_sink_token_transfer_hdfs_dev:
	http :8083/connectors/token-transfer-hdfs-sink-dev/status -b

pause_sink_token_transfer_hdfs_dev:
	http PUT :8083/connectors/token-transfer-hdfs-sink-dev/pause -b

stop_sink_token_transfer_hdfs_dev:
	http DELETE :8083/connectors/token-transfer-hdfs-sink-dev -b

####################################################################################################
#############################    MANAGE HDFS BLOCKS SINK PROD    ###################################

deploy_sink_blocks_hdfs_prod:
	http PUT :8083/connectors/block-metadata-hdfs-sink-prod/config @connectors/hdfs-sink-prod/block-metadata.json -b

status_sink_blocks_hdfs_prod:
	http :8083/connectors/block-metadata-hdfs-sink-prod/status -b

pause_sink_blocks_hdfs_prod:
	http PUT :8083/connectors/block-metadata-hdfs-sink-prod/pause -b

stop_sink_blocks_hdfs_prod:
	http DELETE :8083/connectors/block-metadata-hdfs-sink-prod -b

####################################################################################################
#############################    MANAGE HDFS BLOCKS SINK PROD    ###################################

deploy_sink_application_logs_hdfs_prod:
	http PUT :8083/connectors/application-logs-hdfs-sink-prod/config @connectors/hdfs-sink-prod/application-logs.json -b

status_sink_application_logs_hdfs_prod:
	http :8083/connectors/application-logs-hdfs-sink-prod/status -b

pause_sink_application_logs_hdfs_prod:
	http PUT :8083/connectors/application-logs-hdfs-sink-prod/pause -b

stop_sink_application_logs_hdfs_prod:
	http DELETE :8083/connectors/application-logs-hdfs-sink-prod -b

####################################################################################################
####################################################################################################
####################################################################################################