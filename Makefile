################################################################################
# dd-chain-explorer — Makefile
# Atalhos para operações de desenvolvimento e deploy.
################################################################################

SHELL := /bin/bash

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

################################################################################
# DABs — Databricks Asset Bundles (bundles atômicos)
#
# Cada componente é um bundle independente em apps/dabs/<component>/
#
# Ordem de deploy:
#   Phase 1: DLT pipelines    — dlt_ethereum, dlt_app_logs
#   Phase 2: batch jobs       — job_ddl_setup, job_delta_maintenance,
#                               job_export_gold, job_reconcile_orphans
#   Phase 3: orchestration    — job_trigger_all, job_full_refresh
#                               (requerem pipeline IDs resolvidos automaticamente)
#   Phase 4: observability    — dashboards (4), alerts (2), genie (1)
#                               (requerem warehouse_id resolvido automaticamente)
#
# Uso rápido (DEV):
#   make dabs_validate_all          → valida todos os 16 bundles
#   make dabs_deploy_all            → deploy completo phases 1-4
#   make dabs_run_ddl_setup         → cria schemas/tabelas (serverless Spark)
#   make dabs_run_dlt_ethereum      → executa pipeline Ethereum
#   make dabs_run_dlt_app_logs      → executa pipeline App Logs
#   make dabs_run_trigger_all       → pipeline sequencial (eth → app_logs)
#   make dabs_check_tables          → verifica row counts Bronze/Silver/Gold
#   make dabs_destroy_all           → destroy de todos os bundles DEV
#   make dabs_drop_catalog          → DROP CASCADE schemas no catálogo DEV
#
# Para target != dev: make dabs_deploy_all DABS_TARGET=hml
################################################################################

DABS_DIR    := apps/dabs
DABS_TARGET ?= dev
DEV_CATALOG ?= dev
DEV_S3_BUCKET ?= dm-chain-explorer-dev-ingestion

# Descobre o ID do primeiro SQL Warehouse disponível (para dashboards/alerts/genie)
_WAREHOUSE_ID = $(shell databricks warehouses list --output json 2>/dev/null \
  | python3 -c "import sys,json; whs=json.load(sys.stdin).get('warehouses',[]); \
    print(next((w['id'] for w in whs),''))" 2>/dev/null)

# ---------- validate -------------------------------------------------------

# Valida todos os 16 bundles DABs (target dev)
dabs_validate_all:
	@echo ">>> Validando todos os bundles DABs (target dev)..."
	@FAILED=""; \
	for d in $(DABS_DIR)/*/; do \
	  name=$$(basename "$$d"); \
	  [[ "$$name" == _* ]] && continue; \
	  [[ ! -f "$$d/databricks.yml" ]] && continue; \
	  printf "  %-40s " "$$name"; \
	  if (cd "$$d" && databricks bundle validate --target dev > /dev/null 2>&1); then \
	    echo "OK"; \
	  else \
	    echo "FAIL"; FAILED="$$FAILED $$name"; \
	  fi; \
	done; \
	if [ -n "$$FAILED" ]; then echo "FAILED:$$FAILED"; exit 1; fi
	@echo ">>> Todos os bundles OK."

# ---------- deploy: individual bundles -------------------------------------

dabs_deploy_dlt_ethereum:
	@echo ">>> Deploy dlt_ethereum (target=$(DABS_TARGET))..."
	cd $(DABS_DIR)/dlt_ethereum && databricks bundle deploy --target $(DABS_TARGET)

dabs_deploy_dlt_app_logs:
	@echo ">>> Deploy dlt_app_logs (target=$(DABS_TARGET))..."
	cd $(DABS_DIR)/dlt_app_logs && databricks bundle deploy --target $(DABS_TARGET)

dabs_deploy_job_ddl_setup:
	@echo ">>> Deploy job_ddl_setup (target=$(DABS_TARGET))..."
	cd $(DABS_DIR)/job_ddl_setup && databricks bundle deploy --target $(DABS_TARGET)

dabs_deploy_job_delta_maintenance:
	@echo ">>> Deploy job_delta_maintenance (target=$(DABS_TARGET))..."
	cd $(DABS_DIR)/job_delta_maintenance && databricks bundle deploy --target $(DABS_TARGET)

dabs_deploy_job_export_gold:
	@echo ">>> Deploy job_export_gold (target=$(DABS_TARGET))..."
	cd $(DABS_DIR)/job_export_gold && databricks bundle deploy --target $(DABS_TARGET)

dabs_deploy_job_reconcile_orphans:
	@echo ">>> Deploy job_reconcile_orphans (target=$(DABS_TARGET))..."
	cd $(DABS_DIR)/job_reconcile_orphans && databricks bundle deploy --target $(DABS_TARGET)

# job_trigger_all e job_full_refresh requerem pipeline IDs resolvidos.
# Os IDs são auto-descobertos via CLI e passados como --var no deploy.
dabs_deploy_job_trigger_all:
	@echo ">>> Resolvendo pipeline IDs para job_trigger_all..."
	$(eval _ETH_ID  := $(shell databricks pipelines list-pipelines --output json 2>/dev/null \
	  | python3 -c "import sys,json; ps=json.load(sys.stdin); \
	    print(next((p['pipeline_id'] for p in ps if p.get('name','').startswith('[dev]') and 'dm-ethereum' in p.get('name','')),''  ))"))
	$(eval _LOGS_ID := $(shell databricks pipelines list-pipelines --output json 2>/dev/null \
	  | python3 -c "import sys,json; ps=json.load(sys.stdin); \
	    print(next((p['pipeline_id'] for p in ps if p.get('name','').startswith('[dev]') and 'dm-app-logs' in p.get('name','')),''))" ))
	@if [ -z "$(_ETH_ID)" ] || [ -z "$(_LOGS_ID)" ]; then \
	  echo "ERRO: pipeline IDs não encontrados. Rode 'make dabs_deploy_phase1' primeiro."; exit 1; \
	fi
	@echo "  pipeline_ethereum_id=$(_ETH_ID)   pipeline_app_logs_id=$(_LOGS_ID)"
	cd $(DABS_DIR)/job_trigger_all && databricks bundle deploy --target $(DABS_TARGET) \
	  --var "pipeline_ethereum_id=$(_ETH_ID)" \
	  --var "pipeline_app_logs_id=$(_LOGS_ID)"

dabs_deploy_job_full_refresh:
	@echo ">>> Resolvendo pipeline IDs para job_full_refresh..."
	$(eval _ETH_ID  := $(shell databricks pipelines list-pipelines --output json 2>/dev/null \
	  | python3 -c "import sys,json; ps=json.load(sys.stdin); \
	    print(next((p['pipeline_id'] for p in ps if p.get('name','').startswith('[dev]') and 'dm-ethereum' in p.get('name','')),''  ))"))
	$(eval _LOGS_ID := $(shell databricks pipelines list-pipelines --output json 2>/dev/null \
	  | python3 -c "import sys,json; ps=json.load(sys.stdin); \
	    print(next((p['pipeline_id'] for p in ps if p.get('name','').startswith('[dev]') and 'dm-app-logs' in p.get('name','')),''))" ))
	@if [ -z "$(_ETH_ID)" ] || [ -z "$(_LOGS_ID)" ]; then \
	  echo "ERRO: pipeline IDs não encontrados. Rode 'make dabs_deploy_phase1' primeiro."; exit 1; \
	fi
	@echo "  pipeline_ethereum_id=$(_ETH_ID)   pipeline_app_logs_id=$(_LOGS_ID)"
	cd $(DABS_DIR)/job_full_refresh && databricks bundle deploy --target $(DABS_TARGET) \
	  --var "pipeline_ethereum_id=$(_ETH_ID)" \
	  --var "pipeline_app_logs_id=$(_LOGS_ID)"

# Deploys todos os 4 dashboards com warehouse_id auto-descoberto
dabs_deploy_dashboards:
	@echo ">>> Deploy dashboards (target=$(DABS_TARGET))..."
	$(eval _WH_ID := $(_WAREHOUSE_ID))
	@for d in dashboard_network_overview dashboard_hot_contracts dashboard_gas_analytics dashboard_api_health; do \
	  echo "  >>> $$d"; \
	  if [ -n "$(_WH_ID)" ]; then \
	    (cd $(DABS_DIR)/$$d && databricks bundle deploy --target $(DABS_TARGET) --var "warehouse_id=$(_WH_ID)"); \
	  else \
	    (cd $(DABS_DIR)/$$d && databricks bundle deploy --target $(DABS_TARGET)); \
	  fi; \
	done
	@echo ">>> Dashboards deployados."

# Deploys ambos os alerts com warehouse_id auto-descoberto
dabs_deploy_alerts:
	@echo ">>> Deploy alerts (target=$(DABS_TARGET))..."
	$(eval _WH_ID := $(_WAREHOUSE_ID))
	@for d in alert_api_keys alert_dynamodb_deadlock; do \
	  echo "  >>> $$d"; \
	  if [ -n "$(_WH_ID)" ]; then \
	    (cd $(DABS_DIR)/$$d && databricks bundle deploy --target $(DABS_TARGET) --var "warehouse_id=$(_WH_ID)"); \
	  else \
	    (cd $(DABS_DIR)/$$d && databricks bundle deploy --target $(DABS_TARGET)); \
	  fi; \
	done
	@echo ">>> Alerts deployados."

# Deploys o Genie space com warehouse_id auto-descoberto
dabs_deploy_genie:
	@echo ">>> Deploy genie_ethereum (target=$(DABS_TARGET))..."
	$(eval _WH_ID := $(_WAREHOUSE_ID))
	@if [ -n "$(_WH_ID)" ]; then \
	  cd $(DABS_DIR)/genie_ethereum && databricks bundle deploy --target $(DABS_TARGET) --var "warehouse_id=$(_WH_ID)"; \
	else \
	  cd $(DABS_DIR)/genie_ethereum && databricks bundle deploy --target $(DABS_TARGET); \
	fi
	@echo ">>> Genie deployado."

# ---------- deploy: phases e all -------------------------------------------

dabs_deploy_phase1: dabs_deploy_dlt_ethereum dabs_deploy_dlt_app_logs
	@echo ">>> Phase 1 OK — DLT pipelines deployed."

dabs_deploy_phase2: dabs_deploy_job_ddl_setup dabs_deploy_job_delta_maintenance dabs_deploy_job_export_gold dabs_deploy_job_reconcile_orphans
	@echo ">>> Phase 2 OK — batch jobs deployed."

dabs_deploy_phase3: dabs_deploy_job_trigger_all dabs_deploy_job_full_refresh
	@echo ">>> Phase 3 OK — orchestration jobs deployed."

dabs_deploy_phase4: dabs_deploy_dashboards dabs_deploy_alerts dabs_deploy_genie
	@echo ">>> Phase 4 OK — observability deployed."

# Deploy completo: Phases 1 → 2 → 3 (auto-resolve pipeline IDs) → 4
dabs_deploy_all: dabs_deploy_phase1 dabs_deploy_phase2 dabs_deploy_phase3 dabs_deploy_phase4
	@echo ""
	@echo "=========================================="
	@echo ">>> Deploy completo OK — 16 componentes."
	@echo "=========================================="

# ---------- run (todos via serverless Spark) --------------------------------

# Cria schemas e tabelas no catálogo DEV via serverless Spark (job-ddl-setup)
dabs_run_ddl_setup:
	@echo ">>> Rodando DDL setup (serverless Spark)..."
	cd $(DABS_DIR)/job_ddl_setup && databricks bundle run --target $(DABS_TARGET) workflow_ddl_setup
	@echo ">>> DDL setup concluído."

# DROP CASCADE + recria todos os schemas/tabelas (preserva dados S3 externos)
# Uso: make dabs_drop_catalog
dabs_drop_catalog:
	@echo ">>> DROP CASCADE schemas no catálogo $(DEV_CATALOG) (serverless Spark)..."
	@echo "    ATENÇÃO: dados S3 externos (raw) NÃO são apagados."
	cd $(DABS_DIR)/job_ddl_setup && databricks bundle run --target $(DABS_TARGET) workflow_ddl_setup \
	  --python-params="--catalog,$(DEV_CATALOG),--lakehouse-s3-bucket,$(DEV_S3_BUCKET),--drop"
	@echo ">>> Drop concluído."

# Executa o pipeline Ethereum via trigger job (serverless DLT)
dabs_run_dlt_ethereum:
	@echo ">>> Rodando pipeline Ethereum (DLT serverless)..."
	cd $(DABS_DIR)/dlt_ethereum && databricks bundle run --target $(DABS_TARGET) workflow_trigger_ethereum
	@echo ">>> Pipeline Ethereum concluído."

# Executa o pipeline App Logs via trigger job (serverless DLT)
dabs_run_dlt_app_logs:
	@echo ">>> Rodando pipeline App Logs (DLT serverless)..."
	cd $(DABS_DIR)/dlt_app_logs && databricks bundle run --target $(DABS_TARGET) workflow_trigger_app_logs
	@echo ">>> Pipeline App Logs concluído."

# Executa o job de delta maintenance (OPTIMIZE + VACUUM — serverless Spark)
dabs_run_delta_maintenance:
	@echo ">>> Rodando Delta Maintenance (serverless Spark)..."
	cd $(DABS_DIR)/job_delta_maintenance && databricks bundle run --target $(DABS_TARGET) workflow_dm_delta_maintenance
	@echo ">>> Delta Maintenance concluído."

# Executa o job de export gold para S3 (serverless Spark)
dabs_run_export_gold:
	@echo ">>> Rodando Export Gold (serverless Spark)..."
	cd $(DABS_DIR)/job_export_gold && databricks bundle run --target $(DABS_TARGET) workflow_dm_export_gold
	@echo ">>> Export Gold concluído."

# Executa dm-trigger-all-dlts: orchestra ethereum → app_logs sequencialmente
dabs_run_trigger_all:
	@echo ">>> Rodando Trigger All DLTs (sequential: ethereum → app_logs)..."
	cd $(DABS_DIR)/job_trigger_all && databricks bundle run --target $(DABS_TARGET) dm-trigger-all-dlts
	@echo ">>> Trigger All concluído."

# Full refresh de ambos os pipelines + export gold (serverless)
dabs_run_full_refresh:
	@echo ">>> Rodando Full Refresh (serverless DLT + Spark)..."
	cd $(DABS_DIR)/job_full_refresh && databricks bundle run --target $(DABS_TARGET) workflow_dlt_full_refresh
	@echo ">>> Full Refresh concluído."

# Reconcilia blocos orphan via notebook serverless.
# Requer: ETHEREUM_RPC_URL=<url> (ex: make dabs_run_reconcile_orphans ETHEREUM_RPC_URL=https://...)
dabs_run_reconcile_orphans:
	@if [ -z "$(ETHEREUM_RPC_URL)" ]; then \
	  echo "AVISO: ETHEREUM_RPC_URL não definido."; \
	  echo "  Uso: make dabs_run_reconcile_orphans ETHEREUM_RPC_URL=https://..."; \
	  exit 1; \
	fi
	@echo ">>> Rodando Reconcile Orphans (serverless Spark)..."
	cd $(DABS_DIR)/job_reconcile_orphans && databricks bundle run --target $(DABS_TARGET) workflow_reconcile_orphans
	@echo ">>> Reconcile Orphans concluído."

# ---------- check tables (serverless Spark) --------------------------------

# Verifica row counts de todas as tabelas Bronze/Silver/Gold via serverless Spark
dabs_check_tables:
	@echo ">>> Verificando row counts (catálogo $(DEV_CATALOG))..."
	cd $(DABS_DIR)/job_ddl_setup && databricks bundle run --target $(DABS_TARGET) workflow_check_tables
	@echo ">>> Check tables concluído."

# ---------- status ----------------------------------------------------------

# Mostra summary dos bundles principais deployados em DEV
dabs_status:
	@echo ">>> Status dos bundles principais..."
	@for d in dlt_ethereum dlt_app_logs job_ddl_setup job_trigger_all; do \
	  echo "=== $$d ==="; \
	  (cd $(DABS_DIR)/$$d && databricks bundle summary --target dev 2>&1 | head -25) || true; \
	  echo ""; \
	done

# ---------- destroy (ordem reversa de dependência) -------------------------

# Destroy de todos os 16 bundles DEV em ordem reversa de dependência
dabs_destroy_all:
	@echo ">>> Destroy ALL DABs bundles (target=dev, ordem reversa)..."
	@for d in genie_ethereum alert_dynamodb_deadlock alert_api_keys \
	           dashboard_api_health dashboard_gas_analytics dashboard_hot_contracts dashboard_network_overview \
	           job_full_refresh job_trigger_all \
	           job_reconcile_orphans job_export_gold job_delta_maintenance job_ddl_setup \
	           dlt_app_logs dlt_ethereum; do \
	  echo "  >>> destroy $$d"; \
	  (cd $(DABS_DIR)/$$d && databricks bundle destroy --target dev --auto-approve 2>&1) || true; \
	done
	@echo ">>> Destroy concluído."


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

