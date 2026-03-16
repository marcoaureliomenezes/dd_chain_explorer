################################################################################
# dd-chain-explorer — Makefile
# Atalhos para operações de desenvolvimento e deploy.
################################################################################

# Faz pull da imagem apache/spark usada pelo spark-master e spark-worker.
# Execute uma vez por máquina: make setup_spark
# setup_spark:
# 	@docker pull apache/spark:3.5.8-scala2.12-java17-python3-ubuntu && echo "apache/spark:3.5.8 pronto."
################################################################################
# DEV: Infraestrutura local (Kafka + Redis + Spark)
# Arquivo: services/dev/compose/local_services.yml
################################################################################

deploy_dev_infra:
	@docker network create vpc_dm 2>/dev/null || true
	@docker compose -f services/dev/compose/local_services.yml up -d


stop_dev_infra:
	@docker compose -f services/dev/compose/local_services.yml down

watch_dev_infra:
	watch docker compose -f services/dev/compose/local_services.yml ps


################################################################################
# DEV: Aplicações Python de captura on-chain
# Arquivo: services/dev/compose/app_services.yml
################################################################################

deploy_dev_stream:
	@docker compose -f services/dev/compose/app_services.yml up -d --build

stop_dev_stream:
	@docker compose -f services/dev/compose/app_services.yml down

watch_dev_stream:
	watch docker compose -f services/dev/compose/app_services.yml ps

################################################################################
# DEV: Jobs Batch Python (kafka maintenance, test api keys)
# Arquivo: services/dev/compose/batch_services.yml
################################################################################

deploy_dev_batch:
	@docker compose -f services/dev/compose/batch_services.yml up --build

stop_dev_batch:
	@docker compose -f services/dev/compose/batch_services.yml down

################################################################################
# DEV: Build de imagens locais usadas pelo DockerOperator do Airflow
# Execute antes de subir o Airflow: make build_local_images
################################################################################

build_local_images:
	@echo ">>> Buildando local/onchain-batch-txs ..."
        @docker build -f docker/onchain-batch-txs/Dockerfile -t local/onchain-batch-txs:latest .
################################################################################
# DEV: Airflow (LocalExecutor)
# Arquivo: services/dev/compose/airflow_services.yml
# Acesso: http://localhost:8090  (admin / admin)
################################################################################

deploy_dev_airflow:
	@docker build -t local/airflow:latest docker/customized/airflow
	@docker compose -f services/dev/compose/airflow_services.yml up airflow-init --exit-code-from airflow-init
	@docker compose -f services/dev/compose/airflow_services.yml up -d airflow-scheduler airflow-webserver

stop_dev_airflow:
	@docker compose -f services/dev/compose/airflow_services.yml down

logs_dev_airflow:
	docker compose -f services/dev/compose/airflow_services.yml logs -f airflow-scheduler airflow-webserver

################################################################################
# PRD: Airflow (LocalExecutor)
# Arquivo: services/prd/compose/airflow_services.yml
# Acesso: http://localhost:8091  (admin / <AIRFLOW_ADMIN_PASSWORD>)
################################################################################

deploy_prd_airflow:
	@docker build -t local/airflow:latest docker/customized/airflow
	@docker compose -f services/prd/compose/airflow_services.yml up airflow-init --exit-code-from airflow-init
	@docker compose -f services/prd/compose/airflow_services.yml up -d airflow-scheduler airflow-webserver

stop_prd_airflow:
	@docker compose -f services/prd/compose/airflow_services.yml down

logs_prd_airflow:
	docker compose -f services/prd/compose/airflow_services.yml logs -f airflow-scheduler airflow-webserver

# Deploy para DEV (Databricks Free Edition)
dabs_deploy_dev:
	cd dabs && databricks bundle deploy --target dev

# Deploy para PROD (normalmente feito via CI/CD)
dabs_deploy_prod:
	cd dabs && databricks bundle deploy --target prod

# Executar um workflow em DEV
# Uso: make dabs_run_dev JOB=dm-ddl-setup
# Jobs disponíveis: dm-ddl-setup, dm-periodic-processing, dm-iceberg-maintenance, dm-teardown
dabs_run_dev:
	cd dabs && databricks bundle run --target dev $(JOB)

# Ver status dos recursos deployados em DEV
dabs_status_dev:
	cd dabs && databricks bundle summary --target dev

# Deploy apenas os dashboards em DEV (auto-descobre o warehouse_id via CLI)
# Requer: databricks CLI autenticado + Python 3
dabs_deploy_dev_dashboards:
	$(eval WAREHOUSE_ID := $(shell cd dabs && databricks warehouses list \
	  --output json 2>/dev/null | python3 -c \
	  "import sys, json; whs=json.load(sys.stdin).get('warehouses',[]); \
	   print(next((w['id'] for w in whs), ''))" 2>/dev/null))
	@if [ -z "$(WAREHOUSE_ID)" ]; then \
	  echo "AVISO: Nenhum SQL Warehouse encontrado. Deployando sem warehouse_id..."; \
	  cd dabs && databricks bundle deploy --target dev; \
	else \
	  echo ">>> Usando warehouse_id=$(WAREHOUSE_ID)"; \
	  cd dabs && databricks bundle deploy --target dev --var warehouse_id=$(WAREHOUSE_ID); \
	fi

################################################################################
# Terraform — atalhos para módulos individuais
# Diretório: terraform/
#
# Autenticação:
#   AWS        → AWS CLI (perfil padrão ou env vars AWS_ACCESS_KEY_ID/SECRET)
#   Databricks → ~/.databrickscfg (config: scripts/setup_databricks_profiles.sh)
#                Env vars em CI/CD: DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID,
#                                   DATABRICKS_CLIENT_SECRET
################################################################################

TF_ARGS ?=
TF_DIR  := services/prd/terraform

# =============================================================================
# GRUPO 1 — Recursos gratuitos: VPC + IAM + S3
# Sem custo na AWS. Podem ficar sempre ativos.
# Apply:   make tf_apply_free_resources
# Destroy: make tf_destroy_free_resources
# =============================================================================

tf_apply_free_resources:
	@echo ">>> Aplicando recursos gratuitos: VPC + IAM + S3 ..."
	cd $(TF_DIR)/1_vpc && terraform apply -auto-approve
	cd $(TF_DIR)/2_iam && terraform apply -auto-approve
	cd $(TF_DIR)/4_s3  && terraform apply -auto-approve
	@echo ">>> Recursos gratuitos: OK"

tf_destroy_free_resources:
	@echo ">>> Destruindo recursos gratuitos: S3 → IAM → VPC ..."
	cd $(TF_DIR)/4_s3  && terraform destroy -auto-approve
	cd $(TF_DIR)/2_iam && terraform destroy -auto-approve
	cd $(TF_DIR)/1_vpc && terraform destroy -auto-approve
	@echo ">>> Recursos gratuitos destruídos."

# =============================================================================
# GRUPO 2 — Recursos AWS pagos: MSK + ElastiCache + ECS
#
# Ordem de apply (dependências):
#   1. MSK (kafka)  e ElastiCache (redis) — sem dependência entre si
#   2. ECS Schema Registry                — precisa do MSK para bootstrapar
#   3. ECS tasks de captura               — precisam do Schema Registry
#
# ATENÇÃO: MSK leva ~20 min para ficar ACTIVE. O apply aguarda automaticamente.
#
# Apply:   make tf_apply_aws_resources
# Destroy: make tf_destroy_aws_resources
# =============================================================================

tf_apply_aws_resources:
	@echo ">>> [1/3] MSK e ElastiCache ..."
	cd $(TF_DIR)/3_msk         && terraform apply -auto-approve
	cd $(TF_DIR)/8_elasticache && terraform apply -auto-approve
	@echo ">>> [2/3] ECS: Schema Registry ..."
	cd $(TF_DIR)/6_ecs && terraform apply -auto-approve \
	  -target=aws_ecs_cluster.dm \
	  -target=aws_ecs_cluster_capacity_providers.dm \
	  -target=aws_cloudwatch_log_group.ecs_apps \
	  -target=aws_service_discovery_private_dns_namespace.dm \
	  -target=aws_service_discovery_service.schema_registry \
	  -target=aws_ecs_task_definition.schema_registry \
	  -target=aws_ecs_service.schema_registry
	@echo ">>> [3/3] ECS: Tasks de captura de dados ..."
	cd $(TF_DIR)/6_ecs && terraform apply -auto-approve
	@echo ">>> Recursos AWS: OK"

tf_destroy_aws_resources:
	@echo ">>> Destruindo recursos AWS: ECS → ElastiCache → MSK ..."
	cd $(TF_DIR)/6_ecs         && terraform destroy -auto-approve
	cd $(TF_DIR)/8_elasticache && terraform destroy -auto-approve
	cd $(TF_DIR)/3_msk         && terraform destroy -auto-approve
	@echo ">>> Recursos AWS destruídos."

# =============================================================================
# GRUPO 3 — Databricks: workspace + Unity Catalog + cluster
#
# Autenticação: perfil [prd] em ~/.databrickscfg
#   Configure com: scripts/setup_databricks_profiles.sh
#   Ou em CI/CD via env vars (veja .github/workflows/deploy_infrastructure.yml)
#
# Apply:   make tf_apply_databricks
# Destroy: make tf_destroy_databricks
# =============================================================================

tf_apply_databricks:
	@echo ">>> Aplicando recursos Databricks ..."
	cd $(TF_DIR)/7_databricks && terraform apply -auto-approve
	@echo ">>> Databricks: OK"

tf_destroy_databricks:
	@echo ">>> Destruindo recursos Databricks ..."
	cd $(TF_DIR)/7_databricks && terraform destroy -auto-approve
	@echo ">>> Databricks destruído."

# =============================================================================
# Deploy / Destroy completo de PRD (todos os grupos em sequência)
# =============================================================================

prod_deploy_infra:
	@echo "===== Deploy completo PRD ====="
	$(MAKE) tf_apply_free_resources
	$(MAKE) tf_apply_aws_resources
	$(MAKE) tf_apply_databricks
	@echo "===== Deploy PRD concluído ====="

prod_destroy_infra:
	@echo "===== Destroy completo PRD ====="
	$(MAKE) tf_destroy_databricks
	$(MAKE) tf_destroy_aws_resources
	$(MAKE) tf_destroy_free_resources
	@echo "===== Destroy PRD concluído ====="

################################################################################
# Schema Registry — sincronização de schemas Avro
#
# Registra todos os schemas Avro do diretório canonical
# (docker/onchain-stream-txs/src/schemas/) em uma instância do
# Confluent Schema Registry, configurando compatibilidade BACKWARD.
#
# Uso:
#   make sync_schemas_dev           # SR local (DEV)
#   make sync_schemas_prod SR_URL=http://<host>:8081  # SR no ECS (PROD via túnel/VPN)
################################################################################

SR_URL ?= http://localhost:8081

sync_schemas_dev:
	@echo ">>> Sincronizando schemas Avro → Schema Registry DEV ($(SR_URL)) ..."
	python scripts/sync_avro_schemas.py --sr-url $(SR_URL)

sync_schemas_prod:
	@if [ -z "$(SR_URL)" ] || [ "$(SR_URL)" = "http://localhost:8081" ]; then \
	  echo "ERRO: passe a URL do SR de PROD: make sync_schemas_prod SR_URL=http://<host>:8081"; \
	  exit 1; \
	fi
	@echo ">>> Sincronizando schemas Avro → Schema Registry PROD ($(SR_URL)) ..."
	python scripts/sync_avro_schemas.py --sr-url $(SR_URL)

# ---------------------------------------------------------------------------
# Inicialização — necessário após clonar o repo ou atualizar providers
# ---------------------------------------------------------------------------

tf_init_prd:
	@for dir in $(TF_DIR)/0_remote_state $(TF_DIR)/1_vpc $(TF_DIR)/2_iam \
	            $(TF_DIR)/3_msk $(TF_DIR)/4_s3 $(TF_DIR)/6_ecs \
	            $(TF_DIR)/7_databricks $(TF_DIR)/8_elasticache; do \
	  echo "=== terraform init: $$dir ==="; \
	  cd $$dir && terraform init -input=false && cd ../..; \
	done

tf_apply_remote_state:
	cd $(TF_DIR)/0_remote_state && terraform apply -auto-approve

# =============================================================================
# TERRAFORM DEV — AWS infra para Databricks Free Edition
# Diretório: services/dev/terraform/
#
# Cria bucket S3 para ingestão Kafka → S3 → Databricks Free Edition.
# Autenticação AWS: usa o perfil local (~/.aws/credentials).
#
# Apply:   make dev_tf_apply
# Destroy: make dev_tf_destroy
# =============================================================================

dev_tf_init:
	cd services/dev/terraform && terraform init -input=false

dev_tf_plan:
	cd services/dev/terraform && terraform plan

dev_tf_apply:
	cd services/dev/terraform && terraform apply -auto-approve

dev_tf_destroy:
	cd services/dev/terraform && terraform destroy -auto-approve

dev_tf_output:
	cd services/dev/terraform && terraform output

# =============================================================================
# DEV: Ingestão Kafka → S3 (Spark local)
#
# Pré-requisitos:
#   1. make dev_tf_apply      (cria bucket S3 + IAM)
#   2. Preencha services/dev/compose/conf/dev.s3.conf com as credenciais
#   3. make deploy_dev_infra  (Kafka + Redis rodando)
#   4. make deploy_dev_stream (apps de captura publicando no Kafka)
#
# O job spark-app-kafka-s3 lê 5 tópicos Kafka e escreve Parquet no S3.
# =============================================================================

start_kafka_s3:
	@echo ">>> Iniciando job Spark: Kafka → S3 multiplex ..."
	@docker compose -f services/dev/compose/app_services.yml up -d spark-app-kafka-s3
	@echo ">>> Job iniciado. Logs: docker logs -f spark-app-kafka-s3"

stop_kafka_s3:
	@docker compose -f services/dev/compose/app_services.yml stop spark-app-kafka-s3

logs_kafka_s3:
	docker logs -f spark-app-kafka-s3

################################################################################
# Build e push de imagens Docker (uso manual; CI/CD faz isso automaticamente)
# Uso: make build_stream VERSION=1.0.0
#      make push_stream  VERSION=1.0.0
#      make build_and_push_stream VERSION=1.0.0
# Se VERSION não for passado, usa 'latest'.
################################################################################

VERSION ?= latest

build_stream:
	docker build -t marcoaureliomenezes/onchain-stream-txs:$(VERSION) ./docker/onchain-stream-txs

build_batch:
	docker build -t marcoaureliomenezes/onchain-batch-txs:$(VERSION) ./docker/onchain-batch-txs

push_stream:
	docker push marcoaureliomenezes/onchain-stream-txs:$(VERSION)

push_batch:
	docker push marcoaureliomenezes/onchain-batch-txs:$(VERSION)

build_and_push_stream: build_stream push_stream

build_and_push_batch: build_batch push_batch

################################################################################
# PROD: Observabilidade — scripts de monitoramento
################################################################################

# Últimas 100 linhas de logs de todas as tasks ECS no cluster de prod
prod_logs_ecs:
	python scripts/prod_ecs_logs.py --lines 100

# Logs de um único serviço: make prod_logs_ecs_svc SVC=dm-mined-txs-crawler
prod_logs_ecs_svc:
	python scripts/prod_ecs_logs.py --lines 100 --service $(SVC)

# Métricas e logs do MSK (janela = 30 min por padrão)
prod_msk_metrics:
	python scripts/prod_msk_metrics.py --minutes 30

# Janela maior: make prod_msk_metrics_1h
prod_msk_metrics_1h:
	python scripts/prod_msk_metrics.py --minutes 60
