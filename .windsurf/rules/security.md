---
trigger: always
---

# Security Rules

## Secrets Management

- **Never** hardcode secrets, API keys, tokens, passwords, or connection strings in source code, Terraform files, or CI/CD workflow files.
- **GitHub Secrets**: all CI/CD credentials are stored as GitHub repository or environment secrets. Reference via `${{ secrets.SECRET_NAME }}`.
- **AWS SSM Parameter Store**: API keys for external services (Etherscan, Alchemy, Infura) are stored in SSM at `/etherscan-api-keys`. Applications read at runtime via `boto3`.
- **Databricks secrets**: not used. DEV uses PAT tokens (env var); PROD uses OAuth M2M service principal (env vars).
- **`.env` files**: gitignored globally (`**/.env`, `**/*.env`). Never commit `.env` files.
- **`secrets.tfvars`**: gitignored globally. Never commit Terraform variable files containing secrets.

## IAM — Least Privilege

- All IAM roles follow least-privilege principle.
- **ECS task execution role**: only ECR pull + CloudWatch Logs write.
- **ECS task role**: scoped to specific DynamoDB tables, S3 buckets, Kinesis streams, SQS queues, SSM parameters, and CloudWatch log groups. Uses resource ARN patterns with environment suffix (e.g., `*-hml`, `*-prd`).
- **Firehose role**: scoped to specific S3 bucket + Kinesis streams.
- **Lambda role**: scoped to specific DynamoDB table, S3 bucket prefix, and CloudWatch Logs.
- **Databricks cross-account role** (PROD): scoped to specific S3 buckets and STS assume-role.

## S3 Security

- **All buckets** have:
  - `block_public_acls = true`
  - `block_public_policy = true`
  - `ignore_public_acls = true`
  - `restrict_public_buckets = true`
  - Server-side encryption (AES256 minimum)
  - Versioning enabled
- **Never** create public S3 buckets.
- **Never** use `s3:*` in IAM policies. Always scope to specific actions and resources.

## Network Security

- **PROD**: ECS tasks run in public subnets with security groups. SG allows only:
  - Ingress: inter-task communication (same SG)
  - Egress: HTTPS (443) to AWS services and external APIs (Web3 providers)
- **HML**: ephemeral security groups per CI/CD run. Same rules as PROD.
- **DEV**: Docker Compose on local network. AWS access via IAM user credentials (`~/.aws`).

## Encryption

- **At rest**: S3 (AES256), DynamoDB (AWS-owned key), Kinesis (server-side encryption optional).
- **In transit**: all AWS SDK calls use TLS by default. Kinesis, SQS, CloudWatch, S3 — all HTTPS.
- **Databricks**: Unity Catalog enforces encryption. External locations use IAM role-based access.

## Credential Rotation

- **Databricks PAT** (DEV): local use via `~/.databrickscfg`. **HML PAT**: store in `DATABRICKS_HML_TOKEN` GitHub secret. Rotate periodically.
- **Databricks OAuth M2M** (PROD): service principal credentials in `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` GitHub secrets.
- **AWS IAM user** (CI/CD): `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in GitHub secrets. Rotate periodically.
- **Etherscan API keys**: stored in SSM. Rotate via AWS Console or CLI.

## Code Review Security Checklist

Before merging any PR, verify:
- [ ] No secrets, tokens, or credentials in code or config files
- [ ] IAM policies use least-privilege (no `*` resources unless justified)
- [ ] S3 buckets have public access block enabled
- [ ] New environment variables don't leak secrets in logs
- [ ] Terraform state is not committed (gitignored)
- [ ] Docker images don't contain embedded secrets (use env vars at runtime)
