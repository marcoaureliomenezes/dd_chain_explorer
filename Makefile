################################################################################
# dd-chain-explorer — Makefile
# Atalhos para operações de desenvolvimento e deploy.
################################################################################

################################################################################
# DEV: Aplicações Python de captura on-chain
# Arquivo: services/dev/00_compose/app_services.yml
################################################################################

deploy_dev_stream:
	@docker compose -f services/dev/00_compose/app_services.yml up -d --build

stop_dev_stream:
	@docker compose -f services/dev/00_compose/app_services.yml down

watch_dev_stream:
	watch docker compose -f services/dev/00_compose/app_services.yml ps

# Deploy para DEV (Databricks Free Edition)
dabs_deploy_dev:
	cd apps/dabs && databricks bundle deploy --target dev

# Deploy para PROD (normalmente feito via CI/CD)
dabs_deploy_prod:
	cd apps/dabs && databricks bundle deploy --target prod

# Executar um workflow em DEV
# Uso: make dabs_run_dev JOB=dm-ddl-setup
# Jobs disponíveis: dm-ddl-setup, dm-batch-contracts, dm-iceberg-maintenance, dm-dlt-full-refresh
dabs_run_dev:
	cd apps/dabs && databricks bundle run --target dev $(JOB)

# Ver status dos recursos deployados em DEV
dabs_status_dev:
	cd apps/dabs && databricks bundle summary --target dev

# Executa dm-trigger-all-dlts em DEV (sequencial: ethereum → app_logs)
# Uso: make run_dev_pipelines
run_dev_pipelines:
	cd apps/dabs && databricks bundle run --target dev dm-trigger-all-dlts

# Pausa o schedule de dm-trigger-all-dlts em DEV antes de um deploy HML
# Uso: make pause_dlt_pipelines
# Para reativar o schedule: make dabs_deploy_dev
pause_dlt_pipelines:
	@cd apps/dabs && \
	JOB_ID=$$(databricks jobs list --output json 2>/dev/null \
	  | python3 -c "import sys,json; jobs=json.load(sys.stdin).get('jobs',[]); \
	    print(next((str(j['job_id']) for j in jobs \
	    if 'dm-trigger-all-dlts' in j.get('settings',{}).get('name','')), ''))"); \
	if [ -z "$$JOB_ID" ]; then \
	  echo "ERRO: job dm-trigger-all-dlts não encontrado. Rode 'make dabs_deploy_dev' primeiro."; exit 1; \
	fi; \
	databricks jobs update $$JOB_ID \
	  --json '{"schedule":{"quartz_cron_expression":"0 0/10 * * * ?","timezone_id":"America/Sao_Paulo","pause_status":"PAUSED"}}' \
	  && echo ">>> Schedule pausado. Para reativar: make dabs_deploy_dev"

# Deploy apenas os dashboards em DEV (auto-descobre o warehouse_id via CLI)
# Requer: databricks CLI autenticado + Python 3
dabs_deploy_dev_dashboards:
	$(eval WAREHOUSE_ID := $(shell cd apps/dabs && databricks warehouses list \
	  --output json 2>/dev/null | python3 -c \
	  "import sys, json; whs=json.load(sys.stdin).get('warehouses',[]); \
	   print(next((w['id'] for w in whs), ''))" 2>/dev/null))
	@if [ -z "$(WAREHOUSE_ID)" ]; then \
	  echo "AVISO: Nenhum SQL Warehouse encontrado. Deployando sem warehouse_id..."; \
	  cd apps/dabs && databricks bundle deploy --target dev; \
	else \
	  echo ">>> Usando warehouse_id=$(WAREHOUSE_ID)"; \
	  cd apps/dabs && databricks bundle deploy --target dev --var warehouse_id=$(WAREHOUSE_ID); \
	fi

# Executa setup DDL no DEV via SQL Warehouse (Free Edition — sem Spark cluster)
# Uso: make dabs_ddl_dev            → cria schemas + tabelas + comentários
#      make dabs_ddl_dev DROP=1     → DROP CASCADE + recria tudo
#      make dabs_ddl_dev COMMENTS=1 → aplica somente comentários
DEV_WAREHOUSE_ID   ?= a2a66f2adb0faf18
DEV_CATALOG        ?= dev
DEV_S3_BUCKET      ?= dm-chain-explorer-dev-ingestion
_DDL_SCRIPT        := apps/dabs/src/batch/ddl/setup_ddl.py
_DDL_BASE_ARGS      = --catalog $(DEV_CATALOG) \
                      --lakehouse-s3-bucket $(DEV_S3_BUCKET) \
                      --warehouse-id $(DEV_WAREHOUSE_ID)

dabs_ddl_dev:
	@if [ "$(DROP)" = "1" ]; then \
	  echo ">>> DROP + setup DDL no DEV (catalog=$(DEV_CATALOG))"; \
	  python3 $(_DDL_SCRIPT) $(_DDL_BASE_ARGS) --drop; \
	elif [ "$(COMMENTS)" = "1" ]; then \
	  echo ">>> Aplicando somente comentários no DEV (catalog=$(DEV_CATALOG))"; \
	  python3 $(_DDL_SCRIPT) $(_DDL_BASE_ARGS) --comments-only; \
	else \
	  echo ">>> Setup DDL no DEV (catalog=$(DEV_CATALOG))"; \
	  python3 $(_DDL_SCRIPT) $(_DDL_BASE_ARGS); \
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
TF_DIR  := services/prd

publish_apps:
	# docker push marcoaureliomenezes/onchain-batch-txs:$(current_branch)
	# docker push marcoaureliomenezes/onchain-stream-txs:$(current_branch)
	docker push marcoaureliomenezes/spark-batch-jobs:$(current_branch)
	# docker push marcoaureliomenezes/spark-streaming-jobs:$(current_branch)

tf_apply_free_resources:
	@echo ">>> Aplicando recursos gratuitos: VPC + peripherals + IAM ..."
	cd $(TF_DIR)/02_vpc         && terraform apply -auto-approve
	cd $(TF_DIR)/04_peripherals && terraform apply -auto-approve
	cd $(TF_DIR)/03_iam         && terraform apply -auto-approve
	@echo ">>> Recursos gratuitos: OK"

deploy_dev_all:
	# docker compose -f services/compose/python_streaming_apps_layer.yml up -d --build
	docker compose -f services/compose/airflow_orchestration_layer.yml up -d --build
	# docker compose -f services/compose/spark_streaming_apps_layer.yml up -d --build

# =============================================================================
# GRUPO 2 — Recursos AWS pagos: Kinesis/SQS + DynamoDB + ECS + Lambda
#
# Ordem de apply (dependências):
#   1. Kinesis/SQS/Firehose/CloudWatch (3_kinesis_sqs)
#   2. DynamoDB (9_dynamodb) — ECS tasks precisam do output dynamodb_table_name
#   3. ECS Fargate (6_ecs) — tasks de captura streaming
#   4. Lambda (10_lambda)
#
# Apply:   make tf_apply_aws_resources
# Destroy: make tf_destroy_aws_resources
# =============================================================================

tf_apply_aws_resources:
	@echo ">>> [1/2] ECS Fargate ..."
	cd $(TF_DIR)/07_ecs    && terraform apply -auto-approve
	@echo ">>> [2/2] Lambda ..."
	cd $(TF_DIR)/06_lambda && terraform apply -auto-approve
	@echo ">>> Recursos AWS: OK"

tf_destroy_aws_resources:
	@echo ">>> Destruindo recursos AWS: Lambda → ECS ..."
	cd $(TF_DIR)/06_lambda && terraform destroy -auto-approve
	cd $(TF_DIR)/07_ecs    && terraform destroy -auto-approve
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
	cd $(TF_DIR)/05_databricks && terraform apply -auto-approve
	@echo ">>> Databricks: OK"

tf_destroy_databricks:
	@echo ">>> Destruindo recursos Databricks ..."
	cd $(TF_DIR)/05_databricks && terraform destroy -auto-approve
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

# ---------------------------------------------------------------------------
# Inicialização PRD — necessário após clonar o repo ou atualizar providers
# ---------------------------------------------------------------------------

tf_init_prd:
	@for dir in $(TF_DIR)/02_vpc $(TF_DIR)/03_iam $(TF_DIR)/04_peripherals \
	            $(TF_DIR)/05_databricks $(TF_DIR)/06_lambda $(TF_DIR)/07_ecs; do \
	  echo "=== terraform init: $$dir ==="; \
	  (cd $$dir && terraform init -input=false); \
	done

tf_apply_remote_state:
	cd $(TF_DIR)/0_remote_state && terraform apply -auto-approve

# =============================================================================
# TERRAFORM DEV — AWS infra para Databricks Free Edition
# Módulos: services/dev/01_peripherals/ + 02_lambda/
#
# Recursos: S3 + Kinesis/SQS + DynamoDB + Lambda + CloudWatch
# Estado:   S3 remoto (bucket dm-chain-explorer-terraform-state, key dev/)
# Autenticação AWS: perfil padrão (~/.aws/credentials)
#
# Apply:   make dev_tf_apply
# Destroy: make dev_tf_destroy
# =============================================================================

DEV_PERIPHERALS_DIR := services/dev/01_peripherals
DEV_LAMBDA_DIR      := services/dev/02_lambda

dev_tf_init:
	cd $(DEV_PERIPHERALS_DIR) && terraform init -input=false
	cd $(DEV_LAMBDA_DIR)      && terraform init -input=false

dev_tf_plan:
	cd $(DEV_PERIPHERALS_DIR) && terraform plan
	cd $(DEV_LAMBDA_DIR)      && terraform plan

dev_tf_apply:
	@echo ">>> [1/2] DEV peripherals ..."
	cd $(DEV_PERIPHERALS_DIR) && terraform apply -auto-approve
	@echo ">>> [2/2] DEV lambda ..."
	cd $(DEV_LAMBDA_DIR)      && terraform apply -auto-approve

dev_tf_destroy:
	@echo ">>> [1/2] DEV lambda ..."
	cd $(DEV_LAMBDA_DIR)      && terraform destroy -auto-approve
	@echo ">>> [2/2] DEV peripherals ..."
	cd $(DEV_PERIPHERALS_DIR) && terraform destroy -auto-approve

dev_tf_output:
	cd $(DEV_PERIPHERALS_DIR) && terraform output
	cd $(DEV_LAMBDA_DIR)      && terraform output

# =============================================================================
# TERRAFORM HML — AWS infra para ambiente de homologação
# Módulos: services/hml/02_vpc/ + 03_iam/ + 04_peripherals/ + 05_databricks/ + 07_ecs/
#
# Estado:   S3 remoto (bucket dm-chain-explorer-terraform-state, key hml/)
# Autenticação AWS: perfil padrão (~/.aws/credentials)
#
# Apply:   make hml_tf_apply
# Destroy: make hml_tf_destroy
# =============================================================================

HML_ROOT := services/hml

hml_tf_init:
	@for dir in $(HML_ROOT)/02_vpc $(HML_ROOT)/03_iam $(HML_ROOT)/04_peripherals \
	            $(HML_ROOT)/05_databricks $(HML_ROOT)/07_ecs; do \
	  echo "=== terraform init: $$dir ==="; \
	  (cd $$dir && terraform init -input=false); \
	done

hml_tf_plan:
	@for dir in $(HML_ROOT)/02_vpc $(HML_ROOT)/04_peripherals $(HML_ROOT)/03_iam \
	            $(HML_ROOT)/07_ecs $(HML_ROOT)/05_databricks; do \
	  echo "=== terraform plan: $$dir ==="; \
	  (cd $$dir && terraform plan); \
	done

hml_tf_apply:
	@echo ">>> [1/3] HML vpc + peripherals (paralelo)..."
	cd $(HML_ROOT)/02_vpc         && terraform apply -auto-approve
	cd $(HML_ROOT)/04_peripherals && terraform apply -auto-approve
	@echo ">>> [2/3] HML iam ..."
	cd $(HML_ROOT)/03_iam         && terraform apply -auto-approve
	@echo ">>> [3/3] HML ecs ..."
	cd $(HML_ROOT)/07_ecs         && terraform apply -auto-approve

hml_tf_destroy:
	@echo ">>> [1/3] HML ecs ..."
	cd $(HML_ROOT)/07_ecs         && terraform destroy -auto-approve
	@echo ">>> [2/3] HML iam ..."
	cd $(HML_ROOT)/03_iam         && terraform destroy -auto-approve
	@echo ">>> [3/3] HML peripherals + vpc ..."
	cd $(HML_ROOT)/04_peripherals && terraform destroy -auto-approve
	cd $(HML_ROOT)/02_vpc         && terraform destroy -auto-approve

hml_tf_output:
	@for dir in $(HML_ROOT)/02_vpc $(HML_ROOT)/03_iam $(HML_ROOT)/04_peripherals \
	            $(HML_ROOT)/07_ecs; do \
	  echo "=== outputs: $$dir ==="; \
	  (cd $$dir && terraform output); \
	done

################################################################################
# Build e push de imagens Docker (uso manual; CI/CD faz isso automaticamente)
# Uso: make build_stream VERSION=1.0.0
#      make push_stream  VERSION=1.0.0
# Se VERSION não for passado, usa 'latest'.
################################################################################

VERSION ?= latest

build_stream:
	docker build -t marcoaureliomenezes/onchain-stream-txs:$(VERSION) ./apps/docker/onchain-stream-txs

push_stream:
	docker push marcoaureliomenezes/onchain-stream-txs:$(VERSION)

build_and_push_stream: build_stream push_stream

################################################################################
# PROD: Observabilidade — scripts de monitoramento
################################################################################

# Últimas 100 linhas de logs de todas as tasks ECS no cluster de prod
prod_logs_ecs:
	python scripts/prod_ecs_logs.py --lines 100

# Logs de um único serviço: make prod_logs_ecs_svc SVC=dm-mined-txs-crawler
prod_logs_ecs_svc:
	python scripts/prod_ecs_logs.py --lines 100 --service $(SVC)

