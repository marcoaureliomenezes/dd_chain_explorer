################################################################################
# dd-chain-explorer — Makefile
# Atalhos para operações de desenvolvimento e deploy.
################################################################################

################################################################################
# DEV: Infraestrutura local (Kafka + DynamoDB)
# Arquivo: services/compose/local_services.yml
################################################################################

deploy_dev_infra:
	@docker network create vpc_dm 2>/dev/null || true
	@docker compose -f services/local_services.yml up -d

# Cria o alias local/spark:3.5 a partir da imagem Spark pre-buildada localmente.
# Necessário antes de subir os serviços Spark (spark-master, spark-worker-1, spark-app-*).
# Execute uma vez por máquina: make setup_spark
setup_spark:
	@docker tag services-spark-master:latest local/spark:3.5 && echo "local/spark:3.5 pronto."
stop_dev_infra:
	@docker compose -f services/local_services.yml down

watch_dev_infra:
	watch docker compose -f services/local_services.yml ps


################################################################################
# DEV: Aplicações Python de captura on-chain
# Arquivo: services/app_services.yml
################################################################################

deploy_dev_stream:
	@docker compose -f services/app_services.yml up -d --build

stop_dev_stream:
	@docker compose -f services/app_services.yml down

watch_dev_stream:
	watch docker compose -f services/app_services.yml ps

################################################################################
# DEV: Jobs Batch Python (kafka maintenance, test api keys)
# Arquivo: services/batch_services.yml
################################################################################

deploy_dev_batch:
	@docker compose -f services/batch_services.yml up --build

stop_dev_batch:
	@docker compose -f services/batch_services.yml down

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

################################################################################
# Terraform — atalhos para módulos individuais
# Diretório: terraform/
################################################################################

tf_init_all:
	@for dir in terraform/0_remote_state terraform/1_vpc terraform/2_iam terraform/3_msk terraform/4_s3 terraform/5_dynamodb terraform/6_ecs terraform/7_databricks; do \
	echo "=== terraform init: $$dir ==="; \
	cd $$dir && terraform init -input=false && cd ../..; \
done

tf_plan_vpc:
	cd terraform/1_vpc && terraform plan

tf_apply_vpc:
	cd terraform/1_vpc && terraform apply

tf_plan_iam:
	cd terraform/2_iam && terraform plan

tf_apply_iam:
	cd terraform/2_iam && terraform apply

tf_plan_msk:
	cd terraform/3_msk && terraform plan

tf_apply_msk:
	cd terraform/3_msk && terraform apply

tf_plan_s3:
	cd terraform/4_s3 && terraform plan

tf_apply_s3:
	cd terraform/4_s3 && terraform apply

tf_plan_dynamodb:
	cd terraform/5_dynamodb && terraform plan

tf_apply_dynamodb:
	cd terraform/5_dynamodb && terraform apply

tf_plan_ecs:
	cd terraform/6_ecs && terraform plan

tf_apply_ecs:
	cd terraform/6_ecs && terraform apply

tf_plan_databricks:
	cd terraform/7_databricks && terraform plan

tf_apply_databricks:
	cd terraform/7_databricks && terraform apply

################################################################################
# Build e push de imagens Docker (uso manual; CI/CD faz isso automaticamente)
################################################################################

current_branch = latest

build_stream:
	docker build -t marcoaureliomenezes/onchain-stream-txs:$(current_branch) ./docker/onchain-stream-txs

build_batch:
	docker build -t marcoaureliomenezes/onchain-batch-txs:$(current_branch) ./docker/onchain-batch-txs

push_stream:
	docker push marcoaureliomenezes/onchain-stream-txs:$(current_branch)

push_batch:
	docker push marcoaureliomenezes/onchain-batch-txs:$(current_branch)
