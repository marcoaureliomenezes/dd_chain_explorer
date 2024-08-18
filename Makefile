DOCKER_NETWORK = docker-hadoop_default
ENV_FILE = hadoop.env
current_branch = 1.0.0


##################################################################################################################################
##################################    COMANDOS PARA CONFIGURAÇÃO DO AMBIENTE    ##################################################

start_cluster_swarm:
	sh scripts/start_cluster_swarm.sh

##################################################################################################################################
#######################    COMANDOS DE INICIALIZAÇÃO DE AMBIENTE DE DESENVOLVIMENTO    ###########################################
##################################################################################################################################

build_app:
	docker build -t marcoaureliomenezes/dm-onchain-batch-txs:$(current_branch) ./docker/app_layer/onchain-batch-txs
	docker build -t marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch) ./docker/app_layer/onchain-stream-txs
	docker build -t marcoaureliomenezes/dm-spark-batch-jobs:$(current_branch) ./docker/app_layer/spark-batch-jobs
	docker build -t marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch) ./docker/app_layer/spark-streaming-jobs

build_lakehouse:
	docker build -t marcoaureliomenezes/hadoop-base:$(current_branch) ./docker/customized/hadoop/base
	docker build -t marcoaureliomenezes/airflow:$(current_branch) ./docker/customized/airflow
	# docker build -t marcoaureliomenezes/dm-postgres:$(current_branch) ./docker/batch_layer/postgres
	# docker build -t marcoaureliomenezes/dm-hue-webui:$(current_branch) ./docker/batch_layer/hue

build_fast:
	# docker build -t marcoaureliomenezes/dm-kafka-connect:$(current_branch) ./docker/fast_layer/kafka-connect

build_ops:
	# docker build -t marcoaureliomenezes/dm-prometheus:$(current_branch) ./docker/ops_layer/prometheus

##################################################################################################################################
#########################	   COMANDOS DE PUBLICAÇÃO DE IMAGENS NO DOCKER-HUB    ##################################################


publish_apps:
	# docker push marcoaureliomenezes/dm-onchain-stream-txs:$(current_branch)
	# docker push marcoaureliomenezes/dm-spark-streaming-jobs:$(current_branch)

publish_fast:
	# docker push dm_data_lake/kafka-connect:$(current_branch)

publish_batch:
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
	# docker push marcoaureliomenezes/dm-prometheus:$(current_branch)

##################################################################################################################################
###################    COMANDOS DE DEPLOY DE CONTAINERS SINGLE NODE COM DOCKER COMPOSE    ########################################

deploy_dev_fast:
	docker compose -f services/compose/fast_services.yml up -d --build

deploy_dev_app:
	docker compose -f services/compose/app_services.yml up -d --build

deploy_dev_lakehouse:
	docker compose -f services/compose/lakehouse_services.yml up -d --build

deploy_dev_ops:
	docker compose -f services/operations/compose_monitoring.yml up -d --build
	
deploy_dev_airflow:
	docker compose -f services/compose/airflow_services.yml up -d

##################################################################################################################################
#########################    COMANDOS DE STOP CONTAINERS EM AMBIENTE DE DESENVOLVIMENTO    #######################################

stop_dev_fast:
	docker compose -f services/compose/fast_services.yml down

stop_dev_app:
	docker compose -f services/compose/app_services.yml down

stop_dev_lakehouse:
	docker compose -f services/compose/lakehouse_services.yml down

stop_dev_ops:
	docker compose -f services/operations/compose_monitoring.yml down

stop_dev_airflow:
	docker compose -f services/compose/airflow_services.yml down

##################################################################################################################################
#########################    COMANDOS DE WATCH CONTAINERS EM AMBIENTE DE DESENVOLVIMENTO    ######################################

watch_dev_fast:
	watch docker compose -f services/compose/fast_services.yml ps

watch_dev_app:
	watch docker compose -f services/compose/app_services.yml ps

watch_dev_lakehouse:
	watch docker compose -f services/compose/lakehouse_services.yml ps

watch_dev_ops:
	watch docker compose -f services/operations/compose_monitoring.yml ps


##################################################################################################################################
#######################    COMANDOS DE INICIALIZAÇÃO DE AMBIENTE DE PRODUÇÃO    ##################################################

# COMANDO DE INICIALIZAÇÃO DO CLUSTER SWARM
start_prod_cluster:
	sh scripts/1_start_cluster_swarm.sh


##################################################################################################################################
#######################    COMANDOS DE DEPLOY DE CONTAINERS EM AMBIENTE DE PRODUÇÃO    ###########################################

deploy_prod_fast:
	docker stack deploy -c services/transactional/swarm_fast.yml layer_fast

deploy_prod_app:
	docker stack deploy -c services/transactional/swarm_apps.yml layer_app

deploy_prod_batch:
	docker stack deploy -c services/data_lake/swarm_hadoop_hive.yml layer_batch

deploy_prod_ops:
	docker stack deploy -c services/operations/swarm_monitoring.yml layer_ops


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

##################################################################################################################################
##########################    COMANDOS DE RELATIVOS A CONECTORES DO KAFKA CONNECT DEV   ##########################################

connect_show_connectors:
	http :8083/connector-plugins -b

##################################################################################################################################
###################################################    HDFS SINK DEV   ###########################################################

##################################################################################################################################
###########################################    CONNECT APPLICATION LOGS HDFS DEV   ###############################################

deploy_sink_application_logs_hdfs_dev:
	http PUT :8083/connectors/application-logs-hdfs-sink-dev/config @connectors/hdfs-sink-dev/application-logs.json -b

status_sink_application_logs_hdfs_dev:
	http :8083/connectors/application-logs-hdfs-sink-dev/status -b

pause_sink_application_logs_hdfs_dev:
	http PUT :8083/connectors/application-logs-hdfs-sink-dev/pause -b

stop_sink_application_logs_hdfs_dev:
	http DELETE :8083/connectors/application-logs-hdfs-sink-dev -b

##################################################################################################################################
##################################################    CONNECT BLOCKS HDFS DEV   ##################################################

deploy_sink_blocks_hdfs_dev:
	http PUT :8083/connectors/block-metadata-hdfs-sink-dev/config @connectors/hdfs-sink-dev/block-metadata.json -b

status_sink_blocks_hdfs_dev:
	http :8083/connectors/block-metadata-hdfs-sink-dev/status -b

pause_sink_blocks_hdfs_dev:
	http PUT :8083/connectors/block-metadata-hdfs-sink-dev/pause -b

stop_sink_blocks_hdfs_dev:
	http DELETE :8083/connectors/block-metadata-hdfs-sink-dev -b

##################################################################################################################################
##################################################    CONNECT CONTRACT CALL HDFS DEV   ###############################################

deploy_sink_contract_call_hdfs_dev:
	http PUT :8083/connectors/contract-call-hdfs-sink-dev/config @connectors/hdfs-sink-dev/contract-call-txs.json -b

status_sink_contract_call_hdfs_dev:
	http :8083/connectors/contract-call-hdfs-sink-dev/status -b

pause_sink_contract_call_hdfs_dev:
	http PUT :8083/connectors/contract-call-hdfs-sink-dev/pause -b

stop_sink_contract_call_hdfs_dev:
	http DELETE :8083/connectors/contract-call-hdfs-sink-dev -b

##################################################################################################################################

deploy_sink_token_transfer_hdfs_dev:
	http PUT :8083/connectors/token-transfer-hdfs-sink-dev/config @connectors/hdfs-sink-dev/token-transfer-txs.json -b

status_sink_token_transfer_hdfs_dev:
	http :8083/connectors/token-transfer-hdfs-sink-dev/status -b

pause_sink_token_transfer_hdfs_dev:
	http PUT :8083/connectors/token-transfer-hdfs-sink-dev/pause -b

stop_sink_token_transfer_hdfs_dev:
	http DELETE :8083/connectors/token-transfer-hdfs-sink-dev -b



##################################################################################################################################
##################################################    HDFS SINK PROD   ###########################################################

deploy_sink_blocks_hdfs_prod:
	http PUT :8083/connectors/block-metadata-hdfs-sink-prod/config @connectors/hdfs-sink-prod/block-metadata.json -b

status_sink_blocks_hdfs_prod:
	http :8083/connectors/block-metadata-hdfs-sink-prod/status -b

pause_sink_blocks_hdfs_prod:
	http PUT :8083/connectors/block-metadata-hdfs-sink-prod/pause -b

stop_sink_blocks_hdfs_prod:
	http DELETE :8083/connectors/block-metadata-hdfs-sink-prod -b

##################################################################################################################################

deploy_sink_application_logs_hdfs_prod:
	http PUT :8083/connectors/application-logs-hdfs-sink-prod/config @connectors/hdfs-sink-prod/application-logs.json -b

status_sink_application_logs_hdfs_prod:
	http :8083/connectors/application-logs-hdfs-sink-prod/status -b

pause_sink_application_logs_hdfs_prod:
	http PUT :8083/connectors/application-logs-hdfs-sink-prod/pause -b

stop_sink_application_logs_hdfs_prod:
	http DELETE :8083/connectors/application-logs-hdfs-sink-prod -b
