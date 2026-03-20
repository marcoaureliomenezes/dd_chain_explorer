################################################################################
# dd-chain-explorer — Makefile
# Atalhos para operações de desenvolvimento e deploy.
################################################################################

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
TF_DIR  := services/prd

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
	@echo ">>> [1/4] Kinesis + SQS + Firehose ..."
	cd $(TF_DIR)/3_kinesis_sqs && terraform apply -auto-approve
	@echo ">>> [2/4] DynamoDB ..."
	cd $(TF_DIR)/9_dynamodb    && terraform apply -auto-approve
	@echo ">>> [3/4] ECS Fargate ..."
	cd $(TF_DIR)/6_ecs         && terraform apply -auto-approve
	@echo ">>> [4/4] Lambda ..."
	cd $(TF_DIR)/10_lambda     && terraform apply -auto-approve
	@echo ">>> Recursos AWS: OK"

tf_destroy_aws_resources:
	@echo ">>> Destruindo recursos AWS: Lambda → DynamoDB → ECS → Kinesis ..."
	cd $(TF_DIR)/10_lambda     && terraform destroy -auto-approve
	cd $(TF_DIR)/9_dynamodb    && terraform destroy -auto-approve
	cd $(TF_DIR)/6_ecs         && terraform destroy -auto-approve
	cd $(TF_DIR)/3_kinesis_sqs && terraform destroy -auto-approve
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

# ---------------------------------------------------------------------------
# Inicialização PRD — necessário após clonar o repo ou atualizar providers
# ---------------------------------------------------------------------------

tf_init_prd:
	@for dir in $(TF_DIR)/0_remote_state $(TF_DIR)/1_vpc $(TF_DIR)/2_iam \
	            $(TF_DIR)/3_kinesis_sqs $(TF_DIR)/4_s3 $(TF_DIR)/6_ecs \
	            $(TF_DIR)/7_databricks $(TF_DIR)/9_dynamodb $(TF_DIR)/10_lambda; do \
	  echo "=== terraform init: $$dir ==="; \
	  (cd $$dir && terraform init -input=false); \
	done

tf_apply_remote_state:
	cd $(TF_DIR)/0_remote_state && terraform apply -auto-approve

# =============================================================================
# TERRAFORM DEV — AWS infra para Databricks Free Edition
# Diretório: services/dev/terraform/1_aws_core/
#
# Recursos: S3 + Kinesis/SQS + DynamoDB + Lambda + CloudWatch
# Estado:   S3 remoto (bucket dm-chain-explorer-terraform-state, key dev/)
# Autenticação AWS: perfil padrão (~/.aws/credentials)
#
# Apply:   make dev_tf_apply
# Destroy: make dev_tf_destroy
# =============================================================================

DEV_TF_DIR := services/dev/terraform/1_aws_core

dev_tf_init:
	cd $(DEV_TF_DIR) && terraform init -input=false

dev_tf_plan:
	cd $(DEV_TF_DIR) && terraform plan

dev_tf_apply:
	cd $(DEV_TF_DIR) && terraform apply -auto-approve

dev_tf_destroy:
	cd $(DEV_TF_DIR) && terraform destroy -auto-approve

dev_tf_output:
	cd $(DEV_TF_DIR) && terraform output

# =============================================================================
# TERRAFORM HML — AWS infra persistente para ambiente de homologação
# Diretório: services/hml/1_aws_core/
#
# Recursos persistentes: S3 (dm-chain-explorer-hml-ingestion) + IAM roles ECS
# Recursos efêmeros (criados/destruídos por CI/CD): Kinesis, SQS, CloudWatch, DynamoDB
# Estado:   S3 remoto (bucket dm-chain-explorer-terraform-state, key hml/)
# Autenticação AWS: perfil padrão (~/.aws/credentials)
#
# Apply:   make hml_tf_apply
# Destroy: make hml_tf_destroy
# =============================================================================

HML_TF_DIR := services/hml/1_aws_core

hml_tf_init:
	cd $(HML_TF_DIR) && terraform init -input=false

hml_tf_plan:
	cd $(HML_TF_DIR) && terraform plan

hml_tf_apply:
	cd $(HML_TF_DIR) && terraform apply -auto-approve

hml_tf_destroy:
	cd $(HML_TF_DIR) && terraform destroy -auto-approve

hml_tf_output:
	cd $(HML_TF_DIR) && terraform output

################################################################################
# Build e push de imagens Docker (uso manual; CI/CD faz isso automaticamente)
# Uso: make build_stream VERSION=1.0.0
#      make push_stream  VERSION=1.0.0
# Se VERSION não for passado, usa 'latest'.
################################################################################

VERSION ?= latest

build_stream:
	docker build -t marcoaureliomenezes/onchain-stream-txs:$(VERSION) ./docker/onchain-stream-txs

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

