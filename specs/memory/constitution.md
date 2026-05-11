# Project Constitution — DD Chain Explorer

> These are the **immutable laws** of dd_chain_explorer. They apply to every change, forever.
> When code conflicts with the constitution, the code is regenerated — never the constitution.

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Streaming | Docker + ECS Fargate | — |
| Messaging | Kinesis PROVISIONED, Firehose Direct Put, SQS | — |
| Storage | S3 (NDJSON, Parquet), DynamoDB (single-table) | — |
| Analytics | Databricks DLT, Unity Catalog, SQL Warehouses | — |
| IaC | Terraform | >= 1.5 (CI: 1.7.0) |
| AWS Provider | hashicorp/aws | >= 5.0 |
| Shared Library | dm-chain-utils (PyPI) | >= 0.2.9 |
| CI/CD | GitHub Actions | — |
| Region | AWS sa-east-1 | — |

---

## Security Non-Negotiables

1. **NEVER hardcode** API keys, tokens, passwords, or connection strings in any file — code, Dockerfile, compose, Makefile, notebook, YAML, or docs.
2. **NEVER commit `.env` with real values** — only `.env.example` with empty placeholders.
3. **NEVER commit** `*.tfstate`, `*.tfstate.backup`, or `secrets.tfvars`.
4. **NEVER embed AWS credentials** (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) in Dockerfiles, compose files, or code.
5. **NEVER create** markdown, JSON, or text files with real secret values, even temporarily.
6. **AWS credentials**: named profiles in `~/.aws/credentials` only; Docker mounts `~/.aws:/root/.aws:ro`.
7. **Databricks credentials**: profiles in `~/.databrickscfg` (`[dev]` PAT, `[prd]` OAuth M2M).
8. **PROD containers**: IAM task roles only — never `AWS_ACCESS_KEY_ID` in production containers.
9. **API keys/tokens at runtime**: read via AWS SSM Parameter Store — containers receive only the SSM path.
10. **IAM policies**: least privilege; never `s3:*` or `iam:*`; all resources scoped by ARN with environment suffix.
11. **S3 buckets**: all four block-public settings must be `true`; AES256 encryption; versioning enabled.
12. **Sensitive outputs**: never print secrets to logs, markdown, or GitHub Actions summaries.

---

## GitFlow

```
master  ← release/{scope}-v{VERSION}   (auto-created by CI only)
  └── develop  ← feature/* | hotfix/*  (all PRs target develop)
```

- `master` and `develop` are protected — **never push directly**.
- `release/*` branches are created automatically by CI — never manually.
- All deploys are triggered via `workflow_dispatch` from branch **`develop`**.
- Deploy scripts include `branch_guard.sh` to enforce this.

### Commit Format

```
<type>(<scope>): <short summary>
```

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `chore` | Maintenance, config, deps |
| `infra` | Terraform changes |
| `ci` | GitHub Actions workflows |
| `docs` | Documentation |
| `refactor` | Refactoring without behavior change |

Valid scopes: `stream`, `batch`, `dlt`, `dabs`, `ecs`, `lambda`, `terraform`, `deps`

---

## Version Management

- `VERSION` at repo root is the **single source of truth** for all deploy pipelines.
- Auto-bumped by CI on PR merge to develop (`bump_version.sh`).
- **NEVER bump VERSION manually** before a deploy — causes duplicate commits.

| Scope | Git Tag |
|-------|---------|
| Streaming apps | `v{VERSION}` |
| DABs | `v{VERSION}-dabs` |
| Lambda | `v{VERSION}-lambda` |
| Infra cloud | `v{VERSION}-infra` |
| Library | `v{VERSION}-lib` |

---

## Python Rules

- **Style**: PEP 8, enforced by linters.
- **Type hints**: required for all public functions and class methods.
- **Imports**: always at top of file, grouped (stdlib → third-party → local).
- **Import path for shared library**:
  ```python
  # ✅ Correct
  from dm_chain_utils.<module> import ClassName
  # ❌ Wrong
  from utils.kinesis import ...
  ```
- **No `console.log` equivalent**: no bare `print()` in production code; use structured logging via `CloudWatchLoggingHandler`.

---

## Terraform Rules

- **Terraform is the only source of truth** — never use AWS Console/CLI to create, modify, or destroy resources.
- All resources must have `common_tags`: `owner`, `managed-by`, `cost-center`, `environment`, `project`.
- Naming convention: `dm-{env}-` or `dm-dd-chain-explorer-{env}-`.
- **Sensitive variables** in `*.tfvars` (gitignored). Commit only `*.tfvars.example` with empty values.
- **PROD apply only via CI/CD** with the `production` approval gate.
- Plan before apply — always. In CI/CD the plan is saved and reviewed before apply.
- PRD deploy module order (must not change):
  ```
  01_tf_state → 02_vpc + 04_peripherals → 03_iam → 05a + 06 + 07 → 05b
  ```

---

## Databricks / DABs Rules

- **`path=` parameter**: NEVER use in `@dlt.table` or `@dlt.view` — Unity Catalog forbids explicit paths.
- **Catalog**: always `${var.catalog}` in YAML — never hardcode catalog names.
- **Bundle variables**: always use `${var.variable_name}` — never hardcode bucket, warehouse_id, or cluster_id.
- **Auto Loader S3 path**: always `s3://{bucket}/raw/{stream-or-prefix}/` — never use `bronze/` as S3 prefix.
- **Targets**: `dev` (Free Edition, local deploy), `hml` (Free Edition, CI/CD only), `prod` (AWS Workspace + Unity Catalog).

---

## S3 Path Convention

- Firehose delivery: `s3://{bucket}/raw/{stream-name}/year=YYYY/month=MM/day=DD/hour=HH/`
- Lambda batch output: `s3://{bucket}/raw/batch/{dataset}/year=YYYY/month=MM/day=DD/`
- Gold exports: `s3://{bucket}/exports/`
- **`bronze/` is a Databricks DLT schema name only — never an S3 prefix.**

---

## DynamoDB Single-Table Keys

Single table `dm-chain-explorer` with `pk` (partition) + `sk` (sort). Entity prefixes:

| Entity | PK prefix | SK |
|--------|-----------|-----|
| Block cache | `BLOCK_CACHE` | `{block_hash}` |
| API semaphore | `SEMAPHORE` | `{api_key_name}` |
| API counter | `COUNTER` | `{api_key_name}` |
| Contract ABI | `ABI` | `{contract_address}` |
| ABI negative cache | `ABI_NEG` | `{contract_address}` |
| Contract metadata | `CONTRACT` | `{contract_address}` |
| Gold consumption | `CONSUMPTION` | `{key_name}` |

---

## Documentation Rules

- `specs/` is the single source of truth for product, architecture and process decisions.
- `docs/` remains intentionally minimal during transition and should only contain a bridge `README.md` pointing to `specs/`.
- READMEs in `apps/` maintain their existing language.
- New detailed documentation should be derived from approved specs before being added.

---

## Medallion Architecture Naming

| Layer | Bronze | Silver | Gold |
|-------|--------|--------|------|
| **Ethereum pipeline** | `b_ethereum` | `s_apps` | `gold`, `g_network` |
| **App logs pipeline** | `b_app_logs` | `s_logs` | `g_api_keys` |

Colors = Databricks schema names. Never mix Silver and Gold in the same schema.

---

## Command Reference

```bash
# DEV streaming
make deploy_dev_stream          # docker compose up --build
make stop_dev_stream            # docker compose down

# DEV infra (Terraform)
make dev_tf_apply               # plan + apply: peripherals + lambda
make dev_tf_destroy             # destroy: lambda → peripherals

# DABs
make dabs_validate_all          # validate all 16 bundles
make dabs_deploy_all            # deploy all phases 1–4
make dabs_run_trigger_all       # trigger ethereum → app_logs pipelines

# PROD observability
make prod_standby               # scale down ECS + pause Databricks
make prod_resume                # scale up ECS + resume Databricks
make prod_logs_ecs              # tail live ECS task logs
```
