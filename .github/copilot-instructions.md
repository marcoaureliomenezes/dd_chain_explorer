# GitHub Copilot Instructions — DD Chain Explorer

Estas instruções guiam o Copilot no contexto do projeto DD Chain Explorer: plataforma de data engineering on-chain (Ethereum) com streaming ECS → Kinesis → Firehose → S3 → Databricks DLT → Gold tables.

---

## Projeto e Estrutura

- **Linguagem principal**: Python 3.12. Terraform HCL para infra. YAML para DABs e CI/CD.
- **Infra**: AWS (ECS Fargate, Kinesis, SQS, Firehose, S3, DynamoDB, Lambda, CloudWatch). Gerenciada 100% via Terraform com remote state em S3 + DynamoDB lock.
- **Processamento**: Databricks DLT (Unity Catalog) com Auto Loader S3. Arquitetura Medallion: Bronze → Silver → Gold.
- **Lambda handlers**: sempre em `lambda/<nome_funcao>/handler.py`.
- **Terraform PROD**: módulos numerados em `services/prd/` (1_vpc → 2_iam → 3_kinesis_sqs → 4_s3 → 6_ecs → 9_dynamodb → 10_lambda).

---

## Regras de Código

### Python
- PEP 8. Type hints em funções públicas. Imports no topo (stdlib → third-party → local).
- DLT: usar `@dlt.table` / `@dlt.view`. **Nunca** usar `path=` em tabelas Unity Catalog.
- Auto Loader: `spark.readStream.format("cloudFiles")` com `cloudFiles.format = "json"` ou `"binaryFile"`.

### Terraform
- Versão >= 1.7.0. Provider AWS >= 5.0.
- Recursos prefixados com `dm-{env}-` ou `dd-chain-explorer-{env}-`.
- Todo recurso deve ter `common_tags` (owner, managed-by, cost-center, environment, project).
- **Nunca** criar recursos AWS via CLI — sempre Terraform + CI/CD.

### Commits
```
<type>(<scope>): <summary>
Types: feat, fix, chore, infra, ci, docs, test, refactor
Scopes: stream, batch, dlt, dabs, ecs, lambda, terraform, deps
```

---

## Segurança

- **Nunca** hardcodar secrets, tokens ou API keys em código, Terraform ou workflows.
- Credenciais CI/CD: GitHub Secrets (`${{ secrets.SECRET_NAME }}`).
- API keys Etherscan: AWS SSM Parameter Store (`/etherscan-api-keys`).
- IAM: sempre least-privilege. Nunca usar `s3:*` ou `*` em recursos.
- S3: todos os buckets com `block_public_acls = true` e AES256 encryption.

---

## CI/CD e Deploy

| Ambiente | Infra | Apps |
|----------|-------|------|
| DEV | `deploy_cloud_infra_dev.yml` | Docker Compose local |
| HML | `deploy_cloud_infra_prd.yml` (persistente) + ephemeral CI/CD | `deploy_streaming_apps.yml`, `deploy_databricks.yml` |
| PRD | `deploy_cloud_infra_prd.yml` | `deploy_streaming_apps.yml`, `deploy_databricks.yml`, `deploy_lambda_functions.yml` |

- **Nunca** fazer deploy manual em HML ou PRD. Sempre via CI/CD.
- GitFlow: `feature/*` → PR → `develop` → CI/CD → `release/*` → PRD (approval) → `master`.
- Bump `VERSION` antes de qualquer deploy pipeline.

---

## FinOps

- Custos documentados em `docs/08_report_finops.md`. Atualizar via `/report-finops`.
- `docs/04_data_ops.md`: arquitetura only — sem informações de custo.
- Região AWS: sempre `sa-east-1` (preços ~50% maiores que us-east-1).
- Antes de adicionar qualquer novo recurso AWS, criar sub-seção em "Avaliação de Novos Recursos" em `08_report_finops.md`.
