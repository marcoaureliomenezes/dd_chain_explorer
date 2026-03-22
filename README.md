# dd-chain-explorer

> **Versão:** `0.2.9` | **Região AWS:** `sa-east-1` | **Branch principal:** `develop`

Pipeline de dados on-chain para extração, processamento e análise de transações Ethereum. Captura dados em tempo real via streaming (ECS Fargate + Kinesis), processa com Delta Live Tables no Databricks e disponibiliza em um lakehouse Delta (Bronze → Silver → Gold) no Unity Catalog.

---

## Arquitetura em Resumo

```
Ethereum APIs (Alchemy/Infura)
        │
        ▼
[ECS Fargate — 5 Python jobs]  ──→  Kinesis Streams  ──→  Firehose  ──→  S3 (raw/)
        │                                                                      │
        └──→  SQS  ──→  DynamoDB (hot data)              Databricks DLT ◄────┘
                                                          (Bronze → Silver → Gold)
                                                                  │
                                          Lambda (Etherscan) ─────┘
```

| Componente | Tecnologia | Localização |
|-----------|-----------|-------------|
| Streaming apps (5 jobs) | Python + ECS Fargate | `apps/docker/onchain-stream-txs/` |
| DLT pipelines + batch workflows | Databricks Asset Bundles | `apps/dabs/` |
| Lambda functions (2) | Python + AWS Lambda | `apps/lambda/` |
| Infra DEV | Terraform (2 módulos) | `services/dev/` |
| Infra PRD | Terraform (8 módulos: 01–07 + 05a/05b) | `services/prd/` |
| Biblioteca compartilhada | `dm-chain-utils` (PyPI) | `utils/` |

---

## Quick Start — DEV

**Pré-requisitos:** Docker, AWS CLI configurado, Databricks CLI, `make`.

```bash
# 1. Provisionar infra DEV na AWS
make tf_apply_dev_peripherals
make tf_apply_dev_lambda

# 2. Subir streaming apps localmente (Docker Compose)
make deploy_dev_stream

# 3. Deploy DABs no workspace DEV
make dabs_deploy_dev
```

Para configurar perfis Databricks e secrets GitHub: ver `scripts/tmp/setup_databricks_profiles.sh` e `scripts/tmp/setup_github_secrets.sh`.

---

## Deploy em Produção

Todos os deploys de PRD são feitos via **GitHub Actions** a partir da branch `develop`.

| Componente | Workflow | Pré-requisito |
|-----------|----------|---------------|
| Infra Cloud (DEV/PRD) | `Deploy Infra Cloud` | Branch `develop`, VERSION não tagueado |
| Streaming apps | `Deploy DM Applications` → `streaming-apps` | Infra PRD deployada |
| DABs Databricks | `Deploy DM Applications` → `databricks-dabs` | Workspace Databricks acessível |
| Lambda functions | `Deploy DM Applications` → `lambda-functions` | IAM roles PRD criados |
| Python lib (`dm-chain-utils`) | `Deploy Python Lib` | PyPI version nova |
| Destruição de infra | `Destroy Infra Cloud` | Digitar `DESTROY` para confirmar |

> Use o workflow `/deploy-infra` no Windsurf para guia interativo de deploy.

---

## Makefile — Referência Rápida

```bash
make help                    # listar todos os targets
make deploy_dev_stream       # Docker Compose DEV (streaming)
make dabs_deploy_dev         # DABs → target dev
make tf_plan_dev_peripherals # Terraform plan DEV/01_peripherals
make tf_apply_dev_lambda     # Terraform apply DEV/02_lambda
make prod_standby            # Pausar ambiente PRD (ECS + Databricks)
make prod_resume             # Retomar ambiente PRD
make prod_ecs_logs           # Ver logs ECS PRD em tempo real
```

---

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [`docs/01_architecture.md`](docs/01_architecture.md) | Arquitetura geral, topologia de rede, segurança |
| [`docs/02_data_capture.md`](docs/02_data_capture.md) | Jobs de streaming, Kinesis, Lambda, DynamoDB |
| [`docs/03_data_processing.md`](docs/03_data_processing.md) | DLT pipelines, modelo Medallion, workflows Databricks |
| [`docs/04_data_ops.md`](docs/04_data_ops.md) | CI/CD, Terraform, DABs, GitFlow, observabilidade |
| [`docs/05_data_serving.md`](docs/05_data_serving.md) | Tabelas Gold, dashboards, APIs |
| [`docs/06_integration_tests_specs.md`](docs/06_integration_tests_specs.md) | Especificações e regras dos testes de integração |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | TODOs, prioridades e dependências |
| [`docs/report_finops.md`](docs/report_finops.md) | Inventário de recursos e custos AWS |
| [`docs/report_security.md`](docs/report_security.md) | Relatório de auditoria de segurança |

**READMEs de componentes:**
- [`apps/docker/README.md`](apps/docker/README.md) — Streaming apps (Kinesis architecture)
- [`apps/dabs/README.md`](apps/dabs/README.md) — Databricks Asset Bundles
- [`apps/lambda/README.md`](apps/lambda/README.md) — Lambda functions

---

## Estrutura do Repositório

```
dd_chain_explorer/
├── apps/
│   ├── dabs/          ← Databricks Asset Bundles (DLT pipelines + workflows)
│   ├── docker/        ← Streaming app container (5 Python jobs)
│   └── lambda/        ← AWS Lambda handlers (2 funções)
├── docs/              ← Documentação técnica
├── scripts/           ← Scripts operacionais permanentes
│   ├── ci/            ← Scripts CI compartilhados (12 scripts)
│   └── tmp/           ← Scripts de setup e utilitários pontuais
├── services/
│   ├── dev/           ← Terraform DEV (2 módulos) + Docker Compose
│   ├── prd/           ← Terraform PRD (8 módulos numerados, incl. 05a/05b)
│   └── modules/       ← Módulos Terraform compartilhados
├── utils/             ← Biblioteca Python compartilhada (dm-chain-utils)
├── Makefile
└── VERSION
```

---

## Versioning & GitFlow

```
master  ←─ release/* (após aprovação PRD)
  └── develop  ←─ feature/*, hotfix/*
```

- Bump `VERSION` antes de qualquer deploy PRD
- Cada pipeline usa suffix de tag: `-infra`, `-dabs`, `-lambda`, `-lib`
- Exemplo: `v0.2.9-infra`, `v0.2.9-dabs`
- Auto-bump de versão via `auto-bump-version.yml` após merge de PRs
