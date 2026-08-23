################################################################################
# dd-chain-explorer — Makefile
#
# Post-capture-retirement scope (v0.5.0): thin wrappers over the scripts CI
# already runs (scripts/ci/*.sh, scripts/build_lambda_layer.sh), plus the
# Databricks Asset Bundle and dev Terraform shortcuts that CI does not drive.
# Capture (blockchain ingestion) lives in the separate dd-chain-capture repo —
# nothing here builds, deploys, or logs a streaming producer.
#
# `make -n <target>` (dry-run) must resolve for every target below — that is
# this file's own acceptance bar (AC-24).
################################################################################

SHELL := /bin/bash

.PHONY: help test lint typecheck check build_lambda_layer \
        dabs_validate_all dabs_deploy_all dabs_destroy_all dabs_run \
        dabs_run_dlt_ethereum dabs_run_dlt_app_logs dabs_run_export_gold \
        dabs_deploy_dashboards dabs_status \
        tf_plan tf_deploy tf_destroy \
        dev_tf_init dev_tf_plan dev_tf_apply dev_tf_destroy dev_tf_output \
        prd_bootstrap_apply

help:
	@echo "dd-chain-explorer — available targets:"
	@echo ""
	@echo "  Quality gates"
	@echo "    make test              - pytest: tests/, scripts/ci/tests"
	@echo "    make lint              - ruff format --check + ruff check (repo-wide)"
	@echo "    make typecheck         - mypy --config-file pyproject.toml (strict scope)"
	@echo "    make check             - lint + typecheck + test"
	@echo ""
	@echo "  Lambda layer"
	@echo "    make build_lambda_layer - scripts/build_lambda_layer.sh (see its docstring)"
	@echo ""
	@echo "  Databricks Asset Bundles (apps/dabs/<bundle>/, default TARGET=dev)"
	@echo "    make dabs_validate_all             - validate every bundle"
	@echo "    make dabs_deploy_all TARGET=dev     - deploy every bundle"
	@echo "    make dabs_destroy_all               - destroy every bundle (target=dev)"
	@echo "    make dabs_run BUNDLE=<name> JOB=<key> TARGET=dev  - run one job/pipeline"
	@echo "    make dabs_run_dlt_ethereum | dabs_run_dlt_app_logs | dabs_run_export_gold"
	@echo "    make dabs_deploy_dashboards TARGET=dev - deploy all 4 dashboards"
	@echo "    make dabs_status                    - summary of the main dev bundles"
	@echo ""
	@echo "  Terraform (hml/prd) — driven by scripts/ci/stack_map.json, same as CI"
	@echo "    make tf_plan ENV=hml|prd            - scripts/ci/plan_env.sh"
	@echo "    make tf_deploy ENV=hml|prd          - scripts/ci/deploy_env.sh"
	@echo "    make tf_destroy ENV=dev|hml|prd [FULL=true] - scripts/ci/destroy_env.sh"
	@echo ""
	@echo "  Terraform (dev) — no CI gate; services/dev/{01_peripherals,02_lambda}"
	@echo "    make dev_tf_init | dev_tf_plan | dev_tf_apply | dev_tf_destroy | dev_tf_output"
	@echo ""
	@echo "  Operator-only, one-time (docs/runbooks/00-bootstrap-apply.md)"
	@echo "    make prd_bootstrap_apply             - services/prd/00_bootstrap (T-A.3)"

################################################################################
# Quality gates — same commands the pre-push chokepoint and plan_on_pr run
################################################################################

test:
	pytest tests scripts/ci/tests -p no:cacheprovider

lint:
	ruff format --check . --no-cache
	ruff check . --no-cache

typecheck:
	mypy --config-file pyproject.toml

check: lint typecheck test

################################################################################
# Lambda layer — scripts/build_lambda_layer.sh (T-D.4)
################################################################################

build_lambda_layer:
	bash scripts/build_lambda_layer.sh

################################################################################
# Databricks Asset Bundles (apps/dabs/<bundle>/)
#
# The bundle set changes across this release (WS-C is actively deleting and
# reshaping bundles) — every target below discovers bundles by globbing
# apps/dabs/*/databricks.yml rather than hardcoding a bundle list, so it
# never goes stale the way the pre-v0.5.0 Makefile did.
################################################################################

DABS_DIR    := apps/dabs
TARGET      ?= dev
DEV_CATALOG ?= dev

dabs_validate_all:
	@echo ">>> Validating every apps/dabs bundle (target=$(TARGET))..."
	@FAILED=""; \
	for d in $(DABS_DIR)/*/; do \
	  name=$$(basename "$$d"); \
	  [[ ! -f "$$d/databricks.yml" ]] && continue; \
	  printf "  %-30s " "$$name"; \
	  if (cd "$$d" && databricks bundle validate --target $(TARGET) > /dev/null 2>&1); then \
	    echo "OK"; \
	  else \
	    echo "FAIL"; FAILED="$$FAILED $$name"; \
	  fi; \
	done; \
	if [ -n "$$FAILED" ]; then echo "FAILED:$$FAILED"; exit 1; fi
	@echo ">>> All bundles OK."

dabs_deploy_all:
	@echo ">>> Deploying every apps/dabs bundle (target=$(TARGET))..."
	@for d in $(DABS_DIR)/*/; do \
	  name=$$(basename "$$d"); \
	  [[ ! -f "$$d/databricks.yml" ]] && continue; \
	  echo "  >>> deploy $$name"; \
	  (cd "$$d" && databricks bundle deploy --target $(TARGET)); \
	done
	@echo ">>> Deploy complete."

dabs_destroy_all:
	@echo ">>> Destroying every apps/dabs bundle (target=$(TARGET))..."
	@for d in $(DABS_DIR)/*/; do \
	  name=$$(basename "$$d"); \
	  [[ ! -f "$$d/databricks.yml" ]] && continue; \
	  echo "  >>> destroy $$name"; \
	  (cd "$$d" && databricks bundle destroy --target $(TARGET) --auto-approve 2>&1) || true; \
	done
	@echo ">>> Destroy complete."

# Run one job or pipeline trigger by its bundle resource key.
# Usage: make dabs_run BUNDLE=dlt_ethereum JOB=workflow_trigger_ethereum
dabs_run:
	@if [ -z "$(BUNDLE)" ] || [ -z "$(JOB)" ]; then \
	  echo "Usage: make dabs_run BUNDLE=<bundle-dir-name> JOB=<resource-key> [TARGET=dev]"; \
	  exit 1; \
	fi
	cd $(DABS_DIR)/$(BUNDLE) && databricks bundle run --target $(TARGET) $(JOB)

dabs_run_dlt_ethereum:
	$(MAKE) dabs_run BUNDLE=dlt_ethereum JOB=workflow_trigger_ethereum TARGET=$(TARGET)

dabs_run_dlt_app_logs:
	$(MAKE) dabs_run BUNDLE=dlt_app_logs JOB=workflow_trigger_app_logs TARGET=$(TARGET)

dabs_run_export_gold:
	$(MAKE) dabs_run BUNDLE=job_export_gold JOB=workflow_dm_export_gold TARGET=$(TARGET)

# Deploys every dashboard_* bundle with the first available SQL Warehouse id
# auto-discovered and passed as --var warehouse_id (falls back to no --var if
# the CLI/warehouse lookup is unavailable, matching each bundle's own default).
dabs_deploy_dashboards:
	@echo ">>> Deploying dashboards (target=$(TARGET))..."
	@_WH_ID=$$(databricks warehouses list --output json 2>/dev/null \
	  | python3 -c "import sys,json; whs=json.load(sys.stdin).get('warehouses',[]); print(next((w['id'] for w in whs),''))" 2>/dev/null); \
	for d in $(DABS_DIR)/dashboard_*/; do \
	  name=$$(basename "$$d"); \
	  echo "  >>> $$name"; \
	  if [ -n "$$_WH_ID" ]; then \
	    (cd "$$d" && databricks bundle deploy --target $(TARGET) --var "warehouse_id=$$_WH_ID"); \
	  else \
	    (cd "$$d" && databricks bundle deploy --target $(TARGET)); \
	  fi; \
	done
	@echo ">>> Dashboards deployed."

dabs_status:
	@echo ">>> Status of the main dev bundles..."
	@for d in dlt_ethereum dlt_app_logs job_export_gold; do \
	  [[ ! -d "$(DABS_DIR)/$$d" ]] && continue; \
	  echo "=== $$d ==="; \
	  (cd $(DABS_DIR)/$$d && databricks bundle summary --target dev 2>&1 | head -25) || true; \
	  echo ""; \
	done

################################################################################
# Terraform — hml/prd, driven by scripts/ci/stack_map.json (same map plan_on_pr
# and the deploy workflow read — no stack name is hardcoded here, see T-A.8).
################################################################################

ENV  ?=
FULL ?= false

tf_plan:
	@if [ -z "$(ENV)" ]; then echo "Usage: make tf_plan ENV=hml|prd"; exit 1; fi
	bash scripts/ci/plan_env.sh $(ENV)

tf_deploy:
	@if [ -z "$(ENV)" ]; then echo "Usage: make tf_deploy ENV=hml|prd"; exit 1; fi
	bash scripts/ci/deploy_env.sh $(ENV)

tf_destroy:
	@if [ -z "$(ENV)" ]; then echo "Usage: make tf_destroy ENV=dev|hml|prd [FULL=true]"; exit 1; fi
	bash scripts/ci/destroy_env.sh $(ENV) $(FULL)

################################################################################
# Terraform — dev (no CI gate; services/dev/{01_peripherals,02_lambda})
################################################################################

DEV_PERIPHERALS_DIR := services/dev/01_peripherals
DEV_LAMBDA_DIR       := services/dev/02_lambda

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

################################################################################
# Operator-only, one-time: the prd/00_bootstrap OIDC stack (T-A.1/T-A.3).
# Never run by CI — see docs/runbooks/00-bootstrap-apply.md before running this.
################################################################################

prd_bootstrap_apply:
	@echo ">>> This applies services/prd/00_bootstrap with YOUR OWN AWS credentials."
	@echo ">>> Read docs/runbooks/00-bootstrap-apply.md first. Ctrl-C now to abort."
	cd services/prd/00_bootstrap && terraform init -input=false && terraform apply
