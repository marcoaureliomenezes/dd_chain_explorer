# dd-chain-explorer

> Region: `sa-east-1` | Default branch: `master` (renaming to `main` at this release's ship — T-A.11) | Active release: see `specs/releases/ACTIVE.md`

An S3-anchored Ethereum data platform: `dd-chain-capture` (a separate repo,
running on a VPS) writes raw blockchain data to this project's S3 raw bucket
— the sole integration boundary. This repository owns everything downstream
of that boundary: Databricks Delta Live Tables (Bronze → Silver → Gold on
Unity Catalog), two AWS Lambda functions, the Terraform that provisions all
of it, and the GitHub Actions CI/CD pipeline. **There is no blockchain
capture code in this repository** — no Kinesis, no Firehose, no SQS, no ECS
producer. Databricks runs on the **Free Edition** (serverless compute only;
no `prod` deployment target exists there).

```
dd-chain-capture (separate repo, VPS)
        │  writes raw JSON
        ▼
   S3 raw bucket  ──────────────────────────────────────┐
        │                                                │
        ▼                                                │
  Databricks DLT (apps/dabs/dlt_*)                        │
  Bronze → Silver → Gold, Unity Catalog                   │
        │                                                 │
        ├──► Lakeview dashboards (apps/dabs/dashboard_*)   │
        │                                                  │
        └──► job_export_gold ──► S3 ──► Lambda ──► DynamoDB │
                                  (apps/lambda/gold_to_dynamodb) │
                                                                  │
  Lambda contracts_ingestion (EventBridge, hourly) ───────────────┘
  Etherscan API → S3 raw/batch/  (a second, independent raw producer)
```

| Component | Technology | Path |
|-----------|-----------|------|
| DLT pipelines + batch jobs + dashboards | Databricks Asset Bundles | `apps/dabs/` |
| Lambda functions (2) | Python 3.12 | `apps/lambda/` |
| Shared library | `dm_chain_utils` — path-installed, never published | `utils/` |
| Infra DEV | Terraform (2 stacks) | `services/dev/` |
| Infra HML | Terraform (1 stack — minimal lane) | `services/hml/` |
| Infra PRD | Terraform (5 stacks incl. the OIDC bootstrap) | `services/prd/` |
| CI/CD | GitHub Actions + `scripts/ci/` | `.github/workflows/`, `scripts/ci/` |

---

## Quick start — quality gates (no cloud credentials needed)

```bash
make check         # ruff format --check + ruff check + mypy + pytest
make test           # pytest: tests/, utils/tests/unit, scripts/ci/tests
make lint            # ruff format --check + ruff check
make typecheck        # mypy --config-file pyproject.toml
```

Every new/kept live-surface module (both Lambda handlers, the 3 live
`dm_chain_utils` modules, `job_export_gold`'s pure functions, the DLT
expectation predicates) has moto-mocked or source-text-contract test
coverage under the repo-level `tests/` tree — see `specs/memory/quality-assurance.md`.

## Building the Lambda layer

```bash
make build_lambda_layer   # scripts/build_lambda_layer.sh — see apps/lambda/README.md
```

## Databricks Asset Bundles

```bash
make dabs_validate_all              # validate every bundle, target=dev
make dabs_deploy_all TARGET=dev     # deploy every bundle
make dabs_run_dlt_ethereum          # trigger the Ethereum DLT pipeline
```

Full bundle-by-bundle reference: [`apps/dabs/README.md`](apps/dabs/README.md).

## Terraform

```bash
make dev_tf_apply                   # DEV — no CI gate, your own AWS credentials
make tf_plan ENV=hml                # HML/PRD — same scripts/ci/plan_env.sh CI runs
make tf_deploy ENV=hml
```

`services/prd/00_bootstrap` is the one stack CI can never apply — see
[`docs/runbooks/00-bootstrap-apply.md`](docs/runbooks/00-bootstrap-apply.md).

`make help` lists every target.

---

## Documentation

The source of truth for product/architecture/tech-stack state is
`specs/memory/**` (Markdown atoms) — read `specs/memory/tech-stack.md` and
`specs/memory/architecture.md` before making a structural change.
`specs/releases/ACTIVE.md` points at the release currently being implemented.

Component READMEs: [`apps/dabs/README.md`](apps/dabs/README.md) ·
[`apps/lambda/README.md`](apps/lambda/README.md) ·
[`utils/README.md`](utils/README.md) · [`docs/README.md`](docs/README.md).

---

## Repository layout

```
dd-chain-explorer/
├── apps/
│   ├── dabs/           ← Databricks Asset Bundles (DLT + batch jobs + dashboards)
│   └── lambda/         ← AWS Lambda handlers (2 functions) + requirements.lock
├── docs/
│   └── runbooks/       ← operator-only, one-time procedures
├── scripts/
│   ├── ci/             ← scripts GitHub Actions runs (not this repo's write set to describe here)
│   └── build_lambda_layer.sh
├── services/
│   ├── dev/            ← Terraform DEV (2 stacks)
│   ├── hml/             ← Terraform HML (1 stack — minimal lane)
│   ├── prd/              ← Terraform PRD (incl. 00_bootstrap, operator-applied)
│   └── modules/           ← shared Terraform modules
├── tests/                    ← repo-level pytest tree (Lambda, utils, DABs pure functions, DLT contracts)
├── utils/                       ← dm_chain_utils shared library
├── Makefile
└── VERSION                        ← single version axis, tracks the SDD release id
```

---

## Versioning

One version axis: `VERSION` (repo root), every `apps/dabs/*/VERSION`, and
`utils/`'s package version all track the SDD release id (`specs/releases/`).
There is no separate artifact-version scheme.
