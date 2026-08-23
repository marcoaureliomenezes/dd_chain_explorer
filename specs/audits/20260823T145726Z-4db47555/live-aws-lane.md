# dd-chain-explorer — Live AWS vs Terraform state vs code — audit lane (2026-08-23)

- Auditor: project-auditor (read-only lane). Account <aws-account-id>, caller `arn:aws:iam::<aws-account-id>:user/dadaia`.
- Regions swept: sa-east-1 (primary), us-east-1 (global/edge), us-west-2 (Databricks quickstart only).
- Repo: `<repo>` @ `c6feb17` (branch `feature/v0.4.0`).
- Method: only `describe/list/get/ls/head`, `aws s3 cp <state> -`, `logs filter-log-events`, CloudWatch metrics, Cost Explorer. No Terraform binary was run. No secret value was read or printed. Scratch: `<workspace>/.dadaia/tmp/project-auditor/20260823/live-aws/` (pulled states, S3 listings, log-group table, CE json).
- Baseline being re-verified: recap audit 2026-08-19.

## 0. Headline

The platform is still **DRY** and its cost has collapsed to **US$ 4.22 month-to-date (Aug), of which the project-attributable part is ~US$ 0.9** (KMS key + S3 cents). Kinesis (US$ 28–32/mo in May/Jun) is gone since July — capture retirement is effective in billing. **Every claim of the 2026-08-19 recap re-verifies unchanged.** New today: **2 stale Terraform state locks since 2026-04-22** (will break the next apply of `prd/databricks-account` and `hml/peripherals`), **24 leaked CI security groups** in the orphan `ChainExplorer-vpc` (the CI secret `HML_VPC_ID` points at that legacy VPC, so it is *not* dead weight — it is silently load-bearing for the hml-apps workflow), **code-ahead-of-state** in `prd/03_iam` (4 GitHub-OIDC roles never applied while the OIDC provider is live) and `prd/07_ecs`, and three orphan IAM roles outside every state. `dd-chain-capture` (VPS) has delivered nothing since 2026-08-19 — nothing since 2026-06-14 in fact; its scraper role was last assumed 2026-07-12.

---

## 1. State inventory — `s3://dm-chain-explorer-terraform-state/` (16 keys, 300,825 B, versioning Enabled, 275 versions, no lifecycle)

| Key | Dir on disk | TF ver | serial | managed res. | Last modified (UTC) | Status |
|---|---|---|---|---|---|---|
| capture/ecr | **none in this repo** | 1.15.2 | 4 | 11 | 2026-06-14 18:06 | **orphan state** (source = dd-chain-capture repo); all 11 resources live |
| dev/lambda | services/dev/02_lambda | 1.7.0 | 6 | 5 | 2026-04-05 21:35 | managed; live |
| dev/peripherals | services/dev/01_peripherals | 1.15.6 | 25 | 8 | 2026-06-23 01:06 | managed; 1 stale object (raw/.keep) |
| hml/databricks-workspace | services/hml/05b_databricks_workspace | 1.7.0 | 10 | 0 | 2026-04-06 02:43 | empty (destroyed) |
| hml/databricks | services/hml/05_databricks | 1.7.0 | 19 | 0 | 2026-04-06 02:44 | empty |
| hml/ecs | services/hml/07_ecs | 1.7.0 | 20 | 0 | 2026-04-06 02:45 | empty — **but cluster `dm-chain-explorer-ecs-hml` is live** |
| hml/iam | services/hml/03_iam | 1.7.0 | 17 | 19 | 2026-04-07 05:22 | managed; all 19 live (never destroyed) |
| hml/peripherals | services/hml/04_peripherals | 1.13.1 | 73 | 2 | 2026-04-22 00:32 | **stale-state**: 2 buckets declared, both 404 live; **stale lock held since 2026-04-22** |
| hml/vpc | services/hml/02_vpc | 1.7.0 | 9 | 0 | 2026-04-06 02:52 | empty — VPC CIDR 10.1.0.0/16 lives on as legacy `ChainExplorer-vpc` (not this lineage) |
| prd/databricks-account | services/prd/05a_databricks_account | 1.7.0 | 12 | 0 | 2026-04-11 06:19 | empty; **stale lock held since 2026-04-22** |
| prd/databricks-workspace | services/prd/05b_databricks_workspace | 1.7.0 | 8 | 0 | 2026-04-11 06:17 | empty |
| prd/ecs | services/prd/07_ecs | 1.7.0 | 12 | 0 | 2026-04-11 06:16 | empty — code declares 6 resources → **code-without-state** |
| prd/iam | services/prd/03_iam | 1.15.2 | 9 | 12 | 2026-05-23 16:26 | managed 12 live; code declares +13 GHA OIDC resources never applied |
| prd/lambda | services/prd/06_lambda | 1.15.2 | 13 | 12 | 2026-05-23 16:27 | managed; all live; schedule ENABLED |
| prd/peripherals | services/prd/04_peripherals | 1.15.6 | 30 | 20 (22 inst.) | 2026-06-23 01:01 | managed; all live |
| prd/vpc | services/prd/02_vpc | 1.7.0 | 8 | 0 | 2026-04-11 06:26 | empty |

Directories without remote state:
- `services/prd/05_databricks` — declares 15 Databricks/S3 resources, backend key `prd/databricks/terraform.tfstate` **does not exist** → never applied; functional duplicate of `05a` + `05b` (**dead code / code-without-state**).
- `services/prd/01_tf_state` — bootstrap (bucket + lock table, `prevent_destroy`), no backend block → local state only; live resources exist (bucket, `dm-chain-explorer-terraform-lock`).
- `services/dev/00_compose` — docker-compose, not Terraform.

Lock table `dm-chain-explorer-terraform-lock` (PAY_PER_REQUEST, 18 items): 16 `-md5` digest rows + **2 real lock rows** (`Operation: Apply`, TF 1.13.1, `Created 2026-04-22T00:16Z` on `prd/databricks-account`, `2026-04-22T00:33Z` on `hml/peripherals`). Any future `apply/plan -lock=true` on those two stacks will fail with "Error acquiring the state lock".

TF version spread: 1.7.0 (CI-era states) / 1.13.1 / 1.15.2 / 1.15.6 (local applies 05-23, 06-14, 06-22). Last CI run in the repo: 2026-04-11 (`Destroy Infra Cloud`); everything written after that was applied locally.

---

## 2. Live inventory

### 2.1 S3 (account has 18 buckets; 5 are project + 2 Databricks-quickstart in us-west-2)

| Bucket | Region | Objects / size | Newest object | Versioning | Lifecycle | State |
|---|---|---|---|---|---|---|
| dm-chain-explorer-raw-data | sa-east-1 | **0 / 0 B** (5 delete markers, all 2026-06-14 `_smoke`/`_provtest` from capture provisioning) | — | Suspended | raw-data-lifecycle | prd/peripherals |
| dm-chain-explorer-dev-ingestion | sa-east-1 | **0 / 0 B** (0 versions) | — | Suspended | expire-dev-data | dev/peripherals (state still declares `raw/.keep` → stale object) |
| dm-chain-explorer-lakehouse | sa-east-1 | 1 / 220 B | 2026-05-23 16:21Z `raw/app_logs/.../firehose-app-logs-prd-1-…gz` (misdirected app-log) | Suspended | lakehouse-ia-lifecycle | prd/peripherals |
| dm-chain-explorer-databricks | sa-east-1 | 3 / 0 B (`.keep` ×3) | 2026-05-23 16:15Z | Suspended | databricks-ia-lifecycle + checkpoints-expiry | prd/peripherals |
| dm-chain-explorer-terraform-state | sa-east-1 | 16 / 300,825 B | 2026-06-23 01:06Z | **Enabled** (275 versions) | none | prd/01_tf_state (local state) |
| databricks-workspace-stack-0dbc7-bucket | us-west-2 | 4 / 1.8 KB (objects 2025-03) | 2025-03-15 | — | — | CFN `databricks-workspace-stack-0dbc7` (not this repo) |
| databricks-workspace-stack-0dbc7-lambdazipsbucket-… | us-west-2 | 1 / 934 KB | 2025-03-14 | — | — | same CFN |

Not project (listed for completeness, untouched): aws-cloudtrail-logs-…, aws-glue-assets-…, burrinhos-barbe-* (3, us-east-1), dadaia-s3-bucket-terraform-rm-state, elasticbeanstalk-sa-east-1-…, marco-menezes.com, marco-menezes-remote-state, portifolio-marco-menezes, stage-portifolio-marco-menezes. (`list-buckets` CreationDate shows 2026-04-23 for several buckets that demonstrably hold older objects — API quirk, not evidence of recreation.)

### 2.2 Lambda / schedules (sa-east-1)

| Function | Runtime | Last modified | 7-day Invocations / Errors | Trigger | State |
|---|---|---|---|---|---|
| dm-dd-chain-explorer-prd-contracts-ingestion | python3.12, 256 MB, 300 s, layer `dm-chain-utils:13` | 2026-05-23 | **168 / 0** (avg 2.85 s, max 3.31 s; every run logs `contracts_processed:0;total_transactions:0;request_count:2`, last 2026-08-23T14:28Z) | EventBridge Scheduler `dm-dd-chain-explorer-prd-contracts-ingestion-hourly` **ENABLED**, `rate(1 hour)` America/Sao_Paulo | prd/lambda |
| dm-dd-chain-explorer-prd-gold-to-dynamodb | python3.12 | 2026-05-23 | no datapoints (never invoked since create; last log 2026-03-23) | S3 notif on `dm-chain-explorer-databricks` `exports/gold_api_keys/*.json` (live, verified) | prd/lambda |
| dm-chain-explorer-gold-to-dynamodb-dev | python3.12 | 2026-04-05 | no datapoints (last log 2026-04-05) | S3 notif on `dm-chain-explorer-dev-ingestion` `exports/gold_api_keys/*.json` (live) | dev/lambda |
| dd-chain-explorer-dev-gold-to-dynamodb | python3.12 | 2026-03-21 | none (last log 2026-03-24) | none | **orphan-live** (legacy, + role `dd-chain-explorer-dev-gold-to-dynamodb-lambda`) |
| HelloWorld, LambdaS3, lambda-sqs, lambda-alb, api-gateway-*-get (6) | py3.10/3.13 | 2025 | HelloWorld **30,240 / 7 d** | EventBridge `InvokeLambdaEveryMinute` ENABLED `rate(1 minute)` | not project (account noise) |
| us-east-1: databricks-workspace-stack-{databricksApiFunction,CopyZipsFunction} | python3.8 (deprecated) | 2022-12-30 | — | CFN | not project |

EventBridge rules sa-east-1: `InvokeLambdaEveryMinute` (→ HelloWorld, ENABLED), `ecs-managed-capacity-provider-rule` (AWS-managed). us-east-1: none. Lambda layers: 1 (`dm-dd-chain-explorer-prd-dm-chain-utils` v13).

Env-var *keys* of prd contracts-ingestion (values not read): CLOUDWATCH_LOG_GROUP, DYNAMODB_TABLE, NETWORK, S3_BUCKET, S3_BUCKET_PREFIX, SSM_ETHERSCAN_PATH — consistent with `services/prd/06_lambda/lambda_contracts_ingestion.tf`.

### 2.3 DynamoDB (sa-east-1)

| Table | Items | Bytes | Billing | PITR | State |
|---|---|---|---|---|---|
| dm-chain-explorer (pk/sk) | **0** | 0 | PAY_PER_REQUEST | ENABLED | prd/peripherals |
| dm-chain-explorer-dev | 0 | 0 | PAY_PER_REQUEST | DISABLED | dev/peripherals |
| dm-chain-explorer-terraform-lock | 18 | 2,498 | PAY_PER_REQUEST | DISABLED | prd/01_tf_state (local) |
| Users | 1 | 40 | provisioned | DISABLED | not project |
| us-east-1: burrinhos-barbe-terraform-locks | — | — | — | — | not project |

### 2.4 ECS / ECR

- Clusters: `dm-chain-explorer-ecs-hml` ACTIVE, 0 services, 0 tasks, 0 container instances, FARGATE/FARGATE_SPOT — **orphan-live** (hml/ecs state = 0 resources). `cluster-docker-on-prem` (ECS Anywhere, CFN 2025-07) — not project; it billed **610.7 instance-hours in July (US$ 6.26) and 179.8 h in Aug (US$ 1.84) until 2026-08-11**, 0 since 08-12.
- Task-definition families (16 families, 63 ACTIVE revisions): `dm-block-data-crawler`, `dm-mined-blocks-watcher`, `dm-mined-txs-crawler`, `dm-orphan-blocks-watcher`, `dm-txs-input-decoder` (12 ACTIVE revs each), `dm-topic-init` (2), `dm-schema-registry`, `hml-dm-*` ×5, `ChainExplorer-onchain-app`, plus non-project. Task definitions are not in any state (registered by the apps-deploy workflow) — zero cost, but a registry of 60 revisions of retired apps.
- ECR sa-east-1: `dd-chain-capture-stream` 0 images, `dd-chain-capture-connect` 0 images (capture/ecr state), `airflow` 1 image 277 MB (2021, not project — the only ECR cost, US$ 0.02–0.03/mo). `prd/07_ecs` code declares ECR `batch`/`stream` — not live.

### 2.5 Network (sa-east-1)

| Resource | Detail | State |
|---|---|---|
| vpc-08d5678158042ea26 `ChainExplorer-vpc` 10.1.0.0/16 | tags Project=ChainExplorer, Environment=dev, ManagedBy=terraform; 4 subnets (public 10.1.1/2, private 10.1.3/4), IGW `ChainExplorer-igw`, 2 route tables, SGs `ChainExplorer-{instances,tasks}-sg-2025071001…`, default SG | **orphan-live** (no state in this bucket; hml/vpc and prd/vpc are 0-resource). CIDR equals `hml/02_vpc` vars. |
| **24 × SG `dm-hml-sg-<GITHUB_RUN_ID>`** in that VPC, description "HML ephemeral SG run=…", ingress tcp 0-65535 self, no tags | run ids 23414748729 … 24176257939 (= `Deploy All DM Applications` runs 2026-03-22 → 2026-04-09) | **orphan-live / leaked**: `scripts/ci/hml_provision.sh` creates them in `$HML_VPC_ID`; `scripts/ci/hml_teardown.sh:41` deletes with `2>/dev/null \|\| true` so every failure was swallowed. Proves the CI secret `HML_VPC_ID` = ChainExplorer-vpc. |
| vpc-51b04f37 default 172.31/16 | 3 subnets, IGW, misc SGs (kafka, EMR, learner…), 3 EFS mount ENIs (fs-0a392866fc881b017, 6 KB) | not project |
| NAT gateways / EIPs / VPC endpoints / ELB / EC2 instances / EBS volumes | **none** | — |

### 2.6 IAM (79 roles in account; 20 carry a project prefix)

| Role | Created | RoleLastUsed | State |
|---|---|---|---|
| dm-dd-chain-explorer-prd-contracts-ingestion-lambda | 2026-05-23 | **2026-08-23 14:28Z** | prd/lambda |
| dm-dd-chain-explorer-prd-eb-contracts-ingestion | 2026-05-23 | 2026-08-23 14:28Z | prd/lambda |
| dm-dd-chain-explorer-prd-gold-to-dynamodb-lambda | 2026-05-23 | never | prd/lambda |
| dm-chain-explorer-{databricks-cluster,databricks-cross-account,ecs-task,ecs-task-execution}-role(-prd) + instance profile -prd | 2026-05-23 | never | prd/iam (12 res.) |
| dm-chain-explorer-{databricks-cluster,databricks-cross-account,ecs-task,ecs-task-execution}-role-hml, -firehose-role-hml, -hml-contracts-ingestion-lambda, -hml-gold-to-dynamodb-lambda + instance profile -hml | 2026-04-07 | ecs/lambda-hml 2026-04-09; others never | hml/iam (19 res., all live) |
| dm-chain-explorer-gold-to-dynamodb-lambda-dev | 2026-04-05 | never | dev/lambda |
| dd-chain-capture-scraper-role | 2026-06-14 | **2026-07-12 12:00Z** | capture/ecr |
| dd-chain-capture-streaming-role | 2026-06-14 | 2026-06-14 | capture/ecr |
| dd-chain-explorer-dev-gold-to-dynamodb-lambda | 2026-03-21 | 2026-03-24 | **orphan** (legacy lambda role) |
| dm-databricks-dev-s3-role (+ inline dm-databricks-dev-s3-policy; tags managed-by=terraform, env=dev; "Databricks Free Edition → S3 DEV") | 2026-02-23 | 2026-05-23 | **orphan** (no state, no code in repo) |
| dm-hml-firehose-role (tags ManagedBy=cicd) | 2026-03-22 | 2026-03-23 | **orphan** |
| gha roles `dm-chain-explorer-gha-{deploy-dev,deploy-hml,deploy-prd,readonly-plan}` | — | — | **code-without-state**: declared in `prd/03_iam/oidc.tf`, not in prd/iam state, not live |

OIDC provider `token.actions.githubusercontent.com` **exists** (operator-created per OP-R6-2). Customer-managed policies with prefix: 0. Instance profiles: 2 (hml, prd). IAM users: dadaia, portifolio-maintainer, user-dremio-dw, user-supplier-001 (not inspected further).

### 2.7 CloudWatch Logs (64 groups sa-east-1, 3 us-east-1)

| Group(s) | Retention | Stored | Last event | State |
|---|---|---|---|---|
| /apps/dm-chain-explorer-prd | 30 d | 0 | none | prd/peripherals |
| /apps/dm-chain-explorer-dev | 3 d | 0 | 2026-06-23 | dev/peripherals |
| /aws/lambda/dm-dd-chain-explorer-prd-contracts-ingestion | **none** | 2.43 MB | 2026-08-23 | implicit (Lambda-created, not in state) |
| /aws/lambda/dm-dd-chain-explorer-prd-gold-to-dynamodb | none | 8 KB | 2026-03-23 | implicit |
| /aws/lambda/dm-chain-explorer-gold-to-dynamodb-dev | none | 2 KB | 2026-04-05 | implicit |
| /aws/lambda/dd-chain-explorer-dev-gold-to-dynamodb | none | 4.6 KB | 2026-03-24 | orphan |
| /aws/lambda/hml-contracts-ingestion-<runid> ×20, /aws/lambda/hml-gold-to-dynamodb-<runid> ×19 | none | ~0.7–2 KB each | 2026-03-22 → 04-09 | **orphan** (CI ephemeral) |
| /aws/ecs/containerinsights/{ChainExplorer-cluster,dm-chain-explorer-ecs-hml,dm-chain-explorer-ecs}/performance | 1 d | 0 | 2025-07-10 / 2026-03-25 / 2026-02-22 | orphan |
| /aws/lambda/HelloWorld | **none** | **738 MB** | 2026-08-23 | not project (grows every minute) |
| /aws-glue/* (5), /ecs/nginxdemos-hello, /ecs/tasl2, misc lambda demos | none | ≤1 MB | 2025 | not project |

### 2.8 SSM / KMS / RolesAnywhere / messaging

- SSM sa-east-1: **27 SecureString params, all `alias/aws/ssm`**: `/etherscan-api-keys/api-key-{1..6}` (LastModified 2026-02-24), `/web3-api-keys/alchemy/api-key-{1..4}`, `/web3-api-keys/infura/api-key-{1..17}` (2026-02-22). us-east-1: 0. No values read. Only `api-key-1` of etherscan is referenced in the hourly lambda logs.
- KMS: 1 customer key `4fdd14ba-…` alias `alias/dd-chain-capture-ssm` ("dd-chain-capture SSM SecureString parameters", Enabled, created 2026-06-14) — **no SSM parameter uses it** (all on the AWS-managed key). Costs US$ 1.00/mo (CE `sa-east-1-KMS-Keys` qty 1 in Jul, 0.72 MTD Aug).
- IAM Roles Anywhere: trust anchor `dd-chain-capture` (2026-05-24) + profiles `dd-chain-capture-scraper-hml`, `dd-chain-capture-streaming-hml` (2026-06-14), all enabled — capture/ecr state. Last assumption 2026-07-12 (scraper).
- SNS: 1 topic `dadaia-sns-topic-suppliers-001` (not project). SQS: `DemoS3Notification`, `lambda-demo-sqs` (not project). **Kinesis: 0. Firehose: 0.** Secrets Manager: 0. Glue: only `default` DB. MSK/RDS/EMR/Redshift/Beanstalk envs/ELB/EC2: none. SageMaker domain `QuickSetupDomain-20250824…` InService (not project, no apps checked). API Gateway: 2 demo APIs (not project). CloudTrail `management-events` multi-region → `aws-cloudtrail-logs-…`.
- CloudFormation: sa-east-1 `Infra-ECS-Cluster-cluster-docker-on-prem-…`, `hello-world-sam`; us-east-1 `databricks-workspace-stack` (2022-12-30); us-west-2 `databricks-workspace-stack-0dbc7` (2025-03-15). None belong to this repo.

### 2.9 Cost (Cost Explorer permitted; UnblendedCost by SERVICE, USD)

| Month | Total | Kinesis | Firehose | ECS | DynamoDB | SQS | S3 | KMS | ECR | Registrar/R53 | Tax |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05 | 62.71 | 28.34 | 0.75 | 4.93 | 2.09 | 1.95 | 0.59 | 0.06 | 0.03 | 16.01 | 7.97 |
| 2026-06 | 50.30 | 31.77 | 0.78 | 4.90 | 2.33 | 2.41 | 0.29 | 0.65 | 0.03 | 1.01 | 6.12 |
| 2026-07 | 9.58 | 0 | 0 | 6.26 (ECS-Anywhere hrs) | 0 | 0 | 0.12 | 1.00 | 0.03 | 1.01 | 1.16 |
| 2026-08 MTD | **4.22** | 0 | 0 | 1.84 (ECS-Anywhere, ends 08-11) | 0 | 0 | 0.09 | 0.72 | 0.02 | 1.01 | 0.49 |

Project-attributable run-rate now ≈ **US$ 1/mo** (KMS key US$ 1 + S3/DynamoDB cents + Lambda/Logs within free tier). The ECS line is the non-project ECS-Anywhere external instance; Kinesis/Firehose/SQS/DynamoDB-on-demand charges stopped with the 2026-06-22 capture destroy.

---

## 3. Drift matrix (live ↔ state ↔ code)

Verdicts: **M** managed-and-coherent · **OL** orphan-live (no state) · **SS** stale-state (state says exists, live doesn't) · **CWS** code-without-state (never applied) · **SWC** state-without-code (state exists, no dir). `$` = cost-bearing.

| Env | Live resource / set | State | Code on disk | Verdict |
|---|---|---|---|---|
| prd | S3 raw-data, lakehouse, databricks (+ lifecycle/PAB/SSE/versioning/ownership, 3 .keep) | prd/peripherals | prd/04_peripherals | M |
| prd | DynamoDB `dm-chain-explorer` (PITR on), LG `/apps/dm-chain-explorer-prd` | prd/peripherals | yes | M |
| prd | Lambda contracts-ingestion + gold-to-dynamodb, layer v13, 3 roles, scheduler hourly, S3 notif | prd/lambda | prd/06_lambda | M (behaviourally idle — 0 contracts since May) |
| prd | 4 roles + 5 inline policies + attachment + instance profile (-prd) | prd/iam | prd/03_iam | M (unused since creation) |
| prd | gha-deploy-dev/hml/prd, gha-readonly-plan roles + 4 policies + 4 attachments + OIDC data | — | prd/03_iam/oidc.tf | **CWS** |
| prd | ECS cluster `dm-chain-explorer-ecs`, ECR batch/stream, SD namespace, LG | prd/ecs (0) | prd/07_ecs | **CWS** (destroyed 04-11, code kept) |
| prd | VPC stack (12 res.) | prd/vpc (0) | prd/02_vpc | CWS (destroyed 04-11) |
| prd | Databricks account/workspace | 05a/05b (0) | 05a, 05b, **05** | CWS; `05_databricks` has no state key at all (dup) |
| prd | Lambda log groups (3, no retention) | — | — | implicit/OL (Lambda-created) |
| prd | TF state bucket + lock table | local only | prd/01_tf_state | M (bootstrap) — **2 stale locks** |
| hml | 19 IAM resources (roles/policies/profile -hml) | hml/iam | hml/03_iam | M (idle since 04-09; iam never destroyed while everything else was) |
| hml | buckets hml-databricks, hml-lakehouse | hml/peripherals (2) | hml/04_peripherals | **SS** (404 live) |
| hml | raw bucket, DynamoDB, LG declared in code | — | hml/04_peripherals | CWS |
| hml | ECS cluster `dm-chain-explorer-ecs-hml` (empty) | hml/ecs (0) | hml/07_ecs | **OL** (cluster survived the destroy) |
| hml | VPC `ChainExplorer-vpc` 10.1.0.0/16 + 4 subnets + IGW + 2 RT + 2 SG | none (legacy "ChainExplorer" lineage, 2025-07) | hml/02_vpc declares same CIDR via module | **OL** (no NAT/EIP → US$ 0; but load-bearing for CI via `HML_VPC_ID`) |
| hml | 24 × `dm-hml-sg-<run>` | none | scripts/ci/hml_provision.sh | **OL / leaked** |
| hml | 39 × `/aws/lambda/hml-*-<run>` log groups, 3 containerinsights groups | none | — | OL (≈35 KB, cents) |
| hml | hml-dm-* task-definition families (5) | none | — | OL (free) |
| hml | role `dm-hml-firehose-role` | none | none | **OL** |
| dev | bucket dev-ingestion (+PAB/SSE/versioning/lifecycle), DynamoDB -dev, LG /apps/…-dev | dev/peripherals | dev/01_peripherals | M |
| dev | s3_object `raw/.keep` in dev-ingestion | dev/peripherals | module s3 | **SS** (bucket has 0 objects) |
| dev | Lambda gold-to-dynamodb-dev + role/policy + permission + notif | dev/lambda | dev/02_lambda | M |
| dev | Lambda `dd-chain-explorer-dev-gold-to-dynamodb` + role + LG | none | none | **OL** (legacy, pre-rename) |
| dev | role `dm-databricks-dev-s3-role` (+ inline policy; "Databricks Free Edition → S3 DEV") | none | none | **OL** (last used 2026-05-23) |
| x-env | ECR dd-chain-capture-{connect,stream} (0 images), 2 roles+policies, KMS key+alias `$`, trust anchor, 2 profiles | capture/ecr | **none in this repo** | **SWC** (11 res.; managed elsewhere) |
| x-env | 27 SSM SecureString params | none | referenced by code (SSM_ETHERSCAN_PATH) | OL (operator-managed secrets; acceptable) |
| x-env | OIDC provider github | none | referenced as data source | OL by design (OP-R6-2) |
| acct | HelloWorld every-minute rule + 738 MB log group; ECS-Anywhere hours (to 08-11) `$`; Databricks quickstart CFN ×2 + buckets + py3.8 lambdas; SageMaker domain; EFS; Glue logs | n/a | n/a | not project — reported as account hygiene |

Cost-bearing orphans/oddities: KMS `alias/dd-chain-capture-ssm` (US$ 1/mo, protects nothing); ECS-Anywhere instance (not project, now 0 h/day); HelloWorld log storage (~US$ 0.02/mo, growing). Everything else orphaned is free but noisy.

---

## 4. Data freshness

| Bucket / prefix | Count | Newest object | Since 2026-08-19? |
|---|---|---|---|
| dm-chain-explorer-raw-data (all prefixes) | 0 (5 delete markers 2026-06-14: `raw/mainnet-blocks-data/_smoke.txt`, `raw/app_logs/_provtest.txt`, `raw/scraped-sandbox/_serve-smoke.txt` …) | — | **No** |
| dm-chain-explorer-dev-ingestion | 0 (0 versions) | — | No |
| dm-chain-explorer-lakehouse `raw/app_logs/year=2026/month=05/day=23/` | 1 × 220 B | 2026-05-23 16:21Z | No |
| dm-chain-explorer-databricks `checkpoints/ staging/ unity-catalog/` | 3 × 0 B `.keep` | 2026-05-23 16:15Z | No |
| dm-chain-explorer-terraform-state | 16 | 2026-06-23 01:06Z (dev/peripherals) | No |
| DynamoDB dm-chain-explorer / -dev | 0 / 0 items | — | No |
| dd-chain-capture (VPS) signals | ECR 0 images both repos; `dd-chain-capture-scraper-role` LastUsed **2026-07-12**, streaming-role 2026-06-14; raw-data delete markers 2026-06-14 | — | **Nothing delivered since 2026-08-19 — nor since 2026-06-14.** |
| Lambda contracts-ingestion logs | 168 runs/7 d | 2026-08-23 14:28Z — each `contracts_processed:0` | only log noise, no data |

---

## 5. Findings

| ID | Sev | Env | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| LA-01 | HIGH | prd/hml | **2 stale Terraform state locks** held since 2026-04-22 (Apply, TF 1.13.1) on `prd/databricks-account` and `hml/peripherals`; next apply on those stacks fails | `dynamodb scan dm-chain-explorer-terraform-lock` → 2 non-md5 rows, Created 2026-04-22T00:16Z / 00:33Z | Operator: `terraform force-unlock <ID>` (or delete the 2 rows) after confirming no run is live; add lock-age check to `tf_state_lock_check.sh` |
| LA-02 | HIGH | hml | **24 leaked CI security groups** `dm-hml-sg-<run>` in `ChainExplorer-vpc`; teardown swallows failures (`\|\| true`); the CI secret `HML_VPC_ID` targets the legacy VPC, so the "orphan" VPC is actually the hml-apps substrate | `describe-security-groups --filters group-name=dm-hml-sg-*` → 24; `scripts/ci/hml_teardown.sh:41`; SG description "HML ephemeral SG run=…" | Delete the 24 SGs; make teardown fail loudly (retry on DependencyViolation, then fail); decide: either manage `ChainExplorer-vpc` in `hml/vpc` (import) or repoint `HML_VPC_ID` to a TF-managed VPC |
| LA-03 | MED | prd | **Code-without-state**: 4 GitHub-OIDC roles (+4 policies, +4 attachments) in `prd/03_iam/oidc.tf` never applied; OIDC provider exists; CI therefore still cannot assume roles → static keys still in use (SEC-H-02 open in practice) | `iam list-roles` has no `dm-chain-explorer-gha-*`; prd/iam state 12 res.; `list-open-id-connect-providers` → provider present | Apply `prd/03_iam` (plan first; expect +13/0/0) or record the deferral explicitly |
| LA-04 | MED | prd | Hourly `contracts-ingestion` still ENABLED and idle: 168 inv/7 d, `contracts_processed:0` every run, DynamoDB 0 items; burns Etherscan quota + logs (2.4 MB, no retention) | scheduler `rate(1 hour)` ENABLED; CloudWatch metrics; log tail 2026-08-23 14:28Z | Disable the schedule (state `DISABLED` in TF) until capture resumes; set log retention |
| LA-05 | MED | hml | Stale state `hml/peripherals`: declares 2 buckets that are 404; code declares 5 modules; `hml/iam` keeps 19 live resources for an env whose everything else was destroyed | head-bucket 404 ×2; state 2 res.; hml/iam 19 live, RoleLastUsed ≤ 2026-04-09 | Either destroy hml/iam + `state rm` the 2 phantom buckets (operator), or re-apply hml peripherals; do not leave the env half-alive |
| LA-06 | MED | x-env | `capture/ecr` state (11 res.) lives in this bucket with **no source directory in this repo** (state-without-code); KMS key `alias/dd-chain-capture-ssm` protects **zero** SSM params (all `alias/aws/ssm`) → US$ 1/mo for nothing; 2 ECR repos empty; trust anchor + profiles enabled but unused since 07-12 | `s3 ls` key; `describe-parameters` KeyId column; `describe-images` 0; RoleLastUsed | Move the state to the dd-chain-capture repo's own bucket, or vendor the source here; either use the CMK for the params or drop it (schedule deletion) |
| LA-07 | LOW | dev | Legacy orphans: Lambda `dd-chain-explorer-dev-gold-to-dynamodb` + role + LG (last used 2026-03-24); role `dm-databricks-dev-s3-role` (no state/code, last used 05-23, "Databricks Free Edition → S3 DEV"); role `dm-hml-firehose-role` (ManagedBy=cicd, 03-23) | `list-functions`, `get-role` | Delete the legacy lambda/role/LG; import `dm-databricks-dev-s3-role` into dev (it is the Free-Edition UC credential — keep if Databricks lane needs it) or delete; delete `dm-hml-firehose-role` |
| LA-08 | LOW | hml | 39 `/aws/lambda/hml-*-<run>` + 3 containerinsights log groups, empty ECS cluster `dm-chain-explorer-ecs-hml`, 5 `hml-dm-*` task-def families, 60 ACTIVE `dm-*` task-def revisions — all outside state | `describe-log-groups`, `describe-clusters`, `list-task-definitions` (63 ACTIVE) | Bulk delete LGs + cluster; deregister old task-def revisions; add `hml_teardown` step for per-run log groups |
| LA-09 | LOW | prd | Dead/duplicate code: `prd/05_databricks` (15 res., backend key never created) duplicates `05a`+`05b`; `prd/07_ecs`, `prd/02_vpc`, `05a/05b` all CWS since 04-11; `prd/06_lambda` data source named `kinesis_sqs` now reads `prd/peripherals` (misleading name) | `s3 ls` (no `prd/databricks/`); grep | Remove `05_databricks`; rename the data source; decide whether ECS/VPC/Databricks prd code is "parked" or deleted (document in ARCHITECTURE) |
| LA-10 | LOW | dev | Stale object in state: `dev/peripherals` declares `aws_s3_object raw/.keep` but bucket has 0 keys/0 versions | `list-objects-v2` KeyCount null; state instance present | Next apply will recreate it (harmless) — or drop the prefix object from the module |
| LA-11 | LOW | all | Lambda log groups (prd ×2, dev ×1) have **no retention**; prd TF-managed `/apps/...-prd` has 30 d but the real logs go to `/aws/lambda/...` | `describe-log-groups` retention None | Manage `/aws/lambda/<fn>` LGs in TF with retention (7–30 d) |
| LA-12 | INFO | acct | Non-project account noise worth a separate ticket: `InvokeLambdaEveryMinute` → HelloWorld (30 k inv/7 d, 738 MB log group, no retention); ECS-Anywhere external instance billed until 08-11; Databricks quickstart CFN stacks 2022/2025 with python3.8 lambdas; SageMaker QuickSetup domain; EFS; Glue logs | CE, `list-rules`, `describe-log-groups`, CFN list | Disable the minute rule + set retention; confirm the ECS-Anywhere instance is intentionally deregistered; clean quickstart stacks if the Free-Edition workspace superseded them |
| LA-13 | INFO | x-env | TF version drift across states 1.7.0 → 1.15.6; all post-04-11 applies were local (no CI run since 2026-04-11; `drift_detection.yml` still absent from default branch `master`) | state `terraform_version`; `gh run list` | Pin TF version in CI + `required_version`; merge the workflow into the default branch |

---

## 6. Delta vs 2026-08-19 recap

| Recap claim | Today | Status |
|---|---|---|
| Platform DRY; `raw-data` empty | 0 objects, 5 delete markers (06-14) | unchanged |
| `dev-ingestion` empty | 0 objects / 0 versions | unchanged (+ state still claims `raw/.keep` — newly noted) |
| Last data 2026-05-23 misdirected app-logs in lakehouse | 1 × 220 B, 2026-05-23 16:21Z | unchanged |
| PRD ECS/VPC/Databricks-workspace destroyed 04-11, 0-resource states | prd/ecs, prd/vpc, prd/databricks-{account,workspace} all 0 res., last modified 2026-04-11 | unchanged (+ code still declares them → CWS) |
| Lambda PRD contracts-ingestion hourly ENABLED, `contracts_processed:0` | ENABLED; 168 inv/7 d; 0 errors; 0 contracts at 2026-08-23 14:28Z | unchanged |
| Orphan: ChainExplorer-vpc 10.1.0.0/16 | live, 4 subnets, IGW, no NAT/EIP | unchanged — **changed interpretation**: it hosts 24 leaked CI SGs → CI secret `HML_VPC_ID` points here |
| Orphan: empty ECS cluster dm-chain-explorer-ecs-hml | live, 0/0/0 | unchanged |
| Orphan: legacy Lambda dd-chain-explorer-dev-gold-to-dynamodb | live (2026-03-21), role + LG too | unchanged |
| Orphan: hml-contracts-ingestion-* + containerinsights log groups | 20 + 19 (hml-gold-to-dynamodb-*) + 3 | unchanged |
| hml/peripherals declares 2 deleted buckets | 2 res., both 404 | unchanged |
| hml/iam keeps 19 live IAM resources | 19 in state, all live, unused since 04-09 | unchanged |
| capture/ecr state (11 res.) in this bucket | 11 res., all live; ECR 0 images; scraper role last used 07-12 | unchanged |
| SSM 17 infura + 4 alchemy + 6 etherscan | 27 params, all AWS-managed key, unchanged since Feb | unchanged |
| *(new)* 2 stale TF state locks since 2026-04-22 | LA-01 | **newly found** |
| *(new)* 24 leaked `dm-hml-sg-*` SGs; teardown swallows errors | LA-02 | **newly found** |
| *(new)* prd/03_iam GHA-OIDC roles code-without-state; OIDC provider live | LA-03 | **newly found** |
| *(new)* orphan roles dm-databricks-dev-s3-role, dm-hml-firehose-role | LA-07 | **newly found** |
| *(new)* KMS CMK for capture protects 0 params (US$ 1/mo) | LA-06 | **newly found** |
| *(new)* prd/05_databricks never applied (dup of 05a/05b) | LA-09 | **newly found** |
| *(new)* 60 ACTIVE dm-* task-def revisions, 5 hml-dm-* families | LA-08 | **newly found** |
| *(new)* Cost: May 62.71 → Jun 50.30 → Jul 9.58 → Aug MTD 4.22; Kinesis 0 since Jul; project run-rate ≈ US$ 1/mo | §2.9 | **newly measured** |
| *(new)* Account noise: HelloWorld every-minute + 738 MB LG; ECS-Anywhere hours to 08-11; Databricks quickstart CFN ×2 | LA-12 | **newly found (not project)** |
| dd-chain-capture delivered since 08-19? | No — no object, no role assumption since 07-12 | confirmed |
