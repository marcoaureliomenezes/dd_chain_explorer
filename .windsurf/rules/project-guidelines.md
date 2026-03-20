---
trigger: always
---

# Project Guidelines

## Repository Structure

```
dd_chain_explorer/
├── .github/
│   ├── workflows/              # 7 CI/CD workflows (GitHub Actions)
│   │   ├── deploy_cloud_infra_dev.yml
│   │   ├── deploy_cloud_infra_prd.yml
│   │   ├── deploy_databricks.yml
│   │   ├── deploy_lambda_functions.yml
│   │   ├── deploy_lib_utils.yml
│   │   ├── deploy_streaming_apps.yml
│   │   └── destroy_cloud_infra.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── README.md               # CI/CD docs + secrets reference
├── .windsurf/rules/            # Cascade AI rules (cloud-deploy, project-guidelines, security)
├── dabs/                       # Databricks Asset Bundles
│   ├── databricks.yml          # Bundle config (targets: dev, hml, prod)
│   ├── resources/
│   │   ├── alerts/             # Databricks alert YAMLs
│   │   ├── dashboards/         # Databricks AI/BI dashboard JSONs
│   │   ├── dlt/                # DLT pipeline YAMLs (pipeline_ethereum, pipeline_app_logs)
│   │   ├── genie/              # Databricks Genie space
│   │   └── workflows/          # 10 Databricks workflow YAMLs
│   └── src/
│       ├── streaming/          # DLT notebooks (pipeline_ethereum.py, pipeline_app_logs.py)
│       └── batch/
│           ├── ddl/            # Table DDL scripts (create/drop schemas, views, RLS)
│           ├── maintenance/    # OPTIMIZE, VACUUM, monitoring
│           ├── periodic/       # Hourly batch (Etherscan → S3, export gold)
│           └── batch_contracts/ # Contracts batch ingestion
├── docker/
│   └── onchain-stream-txs/     # Streaming app container (5 Python jobs)
├── docs/                       # Architecture and operational docs
├── lambda/                     # AWS Lambda function handlers
│   ├── contracts_ingestion/    # EventBridge hourly → Etherscan → S3
│   └── gold_to_dynamodb/       # S3 event → DynamoDB sync
├── scripts/
│   ├── environment/            # cleanup_s3.py, cleanup_dynamodb.py
│   ├── hml_integration_test.sh
│   ├── hml_dlt_integration_test.sh
│   ├── dev_dlt_integration_test.sh
│   ├── prod_standby.sh / prod_resume.sh
│   ├── setup_github_secrets.sh / setup_github_environments.sh
│   └── pause_databricks_clusters.py / resume_databricks_clusters.py
├── services/
│   ├── dev/
│   │   ├── compose/            # app_services.yml + conf/dev.dynamodb.conf
│   │   └── terraform/
│   │       └── 1_aws_core/     # Flat module: S3, DynamoDB, Kinesis, SQS, CW Logs, Lambda
│   ├── hml/
│   │   └── 1_aws_core/         # Persistent HML: S3, IAM, CloudWatch Logs + Firehose
│   ├── modules/                # Shared TF modules
│   │   ├── cloudwatch_logs/
│   │   ├── kinesis/
│   │   └── sqs/
│   └── prd/                    # PROD modular Terraform (numbered modules)
│       ├── 0_remote_state/
│       ├── 1_vpc/
│       ├── 2_iam/
│       ├── 3_kinesis_sqs/
│       ├── 4_s3/
│       ├── 6_ecs/
│       ├── 7_databricks/
│       ├── 9_dynamodb/
│       └── 10_lambda/
├── utils/                      # Shared Python library (dm-chain-utils, published to PyPI)
├── Makefile                    # Developer shortcuts
├── VERSION                     # Single version file for all deploy pipelines
└── README.md
```

## Coding Standards

### Python
- **Version**: 3.12
- **Style**: PEP 8, enforced by linters
- **Type hints**: encouraged for public functions
- **Imports**: always at top of file, grouped (stdlib → third-party → local)
- **DLT pipelines**: use `@dlt.table` and `@dlt.view` decorators; never use `path=` parameter (Unity Catalog forbids explicit paths)
- **Auto Loader**: use `spark.readStream.format("cloudFiles")` with `cloudFiles.format` set to `json` or `binaryFile` as needed

### Terraform (HCL)
- **Version**: >= 1.5 (CI uses 1.7.0)
- **Provider**: AWS `>= 5.0` (HML uses `~> 6.36.0`)
- **Backend**: S3 remote state with DynamoDB locking
- **Naming**: resources prefixed with `dm-{env}-` or `dd-chain-explorer-{env}-`
- **Tags**: all resources must have `common_tags` (owner, managed-by, cost-center, environment, project)
- **Modules**: reusable modules in `services/modules/`; environment-specific configs in `services/{env}/`

### YAML (DABs / Workflows)
- **DABs variables**: use `${var.variable_name}` syntax
- **Targets**: `dev` (Free Edition, local deploy), `hml` (Free Edition, CI/CD only), `prod` (AWS workspace)
- **Catalog**: always `${var.catalog}` — never hardcode catalog names
- **path=** parameter: never use in `@dlt.table` / `@dlt.view` (Unity Catalog does not support explicit paths)

## Commit Convention

```
<type>(<scope>): <short summary>

Types: feat, fix, chore, infra, ci, docs, test, refactor
Scopes: stream, batch, dlt, dabs, ecs, lambda, terraform, deps, readme
```

Examples:
```
feat(dlt): add binaryFile Auto Loader for CW Logs double-gzip
fix(batch): handle empty Etherscan response
infra(terraform): add CloudWatch Logs module to HML
ci(deploy): add warehouse_id resolution for HML DABs deploy
```

## GitFlow

```
master  ← release/* (after prod deploy approval)
  └── develop  ← feature/*, hotfix/*
```

- **All PRs target `develop`**. Never push directly to `master` or `develop`.
- **Release branches** (`release/*`) are auto-created by CI after HML integration tests pass.
- **Feature branches**: `feature/<short-description>`
- **Hotfix branches**: `hotfix/<short-description>`

## Version Management

- Single `VERSION` file at repo root governs all deploy pipelines.
- Each pipeline appends a scope suffix to the git tag (`-dabs`, `-infra`, `-lambda`, `-lib`).
- Bump `VERSION` before triggering any deploy workflow.
- For `utils/` library: `VERSION` must match `utils/pyproject.toml` version.

## DLT Pipeline Patterns

### Medallion Architecture
- **Bronze**: raw ingestion from S3 via Auto Loader (`cloudFiles`). One table per Kinesis stream or log source.
- **Silver**: parsed, cleaned, enriched data. JOINs, deduplication, type casting.
- **Gold**: materialized views for consumption. Aggregations, rankings, metrics.

### Naming Convention
- Bronze schemas: `b_ethereum`, `b_app_logs`
- Silver schemas: `s_apps`, `s_logs`
- Gold schemas: `gold`, `g_network`, `g_api_keys`
- Table names: `b_{source}_data` (bronze), descriptive names for silver/gold

### Auto Loader Configuration
- Kinesis streams (NDJSON): `cloudFiles.format = "json"`, `cloudFiles.schemaLocation` auto-managed by DLT
- CloudWatch Logs (double-gzip): `cloudFiles.format = "binaryFile"` + PySpark UDF for decompression
- All Auto Loader sources read from `s3://{bucket}/raw/{stream-or-prefix}/`

## Integration Tests

- **Streaming apps**: `scripts/hml_integration_test.sh` — validates Kinesis, SQS, DynamoDB, Firehose, S3 delivery
- **DLT pipelines**: `scripts/hml_dlt_integration_test.sh` — validates 6 mandatory Gold MVs have row_count > 0
- **DEV DLT**: `scripts/dev_dlt_integration_test.sh` — full end-to-end: deploy DABs + trigger pipelines + validate Gold MVs
- Integration tests **gate** release branch creation in CI/CD. No release without passing tests.
- Integration test rules documented in `docs/integration_test_rules.md`.
