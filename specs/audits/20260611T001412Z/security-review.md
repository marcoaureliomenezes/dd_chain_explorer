# Security Review — dd-chain-explorer

- **Date (UTC):** 2026-06-11T00:14:12Z
- **Reviewer:** security-reviewer (OWASP Top 10 / secrets / IaC / dependency posture)
- **Target:** repo `dd-chain-explorer`, branch `feature/specs-first-docs-cleanup`
- **Platform:** AWS (account region `sa-east-1`) + Databricks, environments dev / hml / prd
- **Scope:** Terraform IaC (`services/`), GitHub Actions (`.github/workflows/`, 7 files), tracked-secret scan, application code (`apps/`, `utils/`), cross-check vs `specs/bugs/*` and `specs/backlog/streaming-jobs-security-hardening.md`.
- **Method:** static read-only review. No exploit code, no scanners run against live systems. All key/secret material redacted to `[REDACTED]`.
- **Authorization:** Operator-requested full audit of his own project.

> **Disclaimer.** This is a point-in-time snapshot. No codebase is ever declared "fully secure". `pip-audit`/`npm audit` were NOT run (no local venv available; see CVE section).

---

## Scan summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 5 |
| LOW | 5 |
| INFO | 3 |

**Tools / passes run:** manual OWASP Top-10 walk; `git grep` secret-pattern scan; `git ls-files` tracked-sensitive-file scan; Terraform module + per-env review (IAM, S3, DynamoDB, Kinesis, SQS, ECS, VPC/SG, Databricks, tf_state backend); GitHub Actions trigger / permissions / credential / injection / action-pinning review; app-code TLS / deserialization / secret-logging scan.

**Headline:** Two HIGH findings — (1) raw Web3/Infura API keys logged in cleartext to CloudWatch and then propagated into the S3/Databricks log lakehouse (a class the prior streaming review missed), and (2) long-lived static AWS access keys used across every deploy/plan workflow instead of OIDC, including on a `pull_request`-triggered plan job. No live secret values are committed to the repo. Terraform module hygiene is generally strong (resource-scoped IAM, S3 public-access-blocked + encrypted + versioned, state bucket encrypted + locked, all third-party Actions SHA-pinned).

---

## OWASP findings

### HIGH

#### H-01 — Raw Web3/Infura API key logged in cleartext (propagates to log lakehouse)
- **CWE:** CWE-532 (Insertion of Sensitive Information into Log File)
- **OWASP:** A09:2021 Security Logging & Monitoring Failures
- **Severity:** HIGH
- **Location:**
  - `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py:66`
  - `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py:107`
  - `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py:114`
- **Evidence (redacted):**
  - `:66` — `self.logger.warning(f"Rate limit (429) na key {actual_api_key}, ...")`
  - `:107` — `self.logger.info(f"API KEY {actual_api_key} is being used by another process.")`
  - `:114` — `self.logger.info(f"API KEY {actual_api_key} reached throughput threshold.")`
  - `actual_api_key` is the **raw secret**, not an identifier: it is the value returned by `elect_new_api_key()` and passed straight to `self.web3.get_node_connection(actual_api_key, 'infura')` (`:49, :83, :111, :119`) to build the authenticated RPC URL. Value redacted: `[REDACTED]`.
- **Description:** Three log statements emit the full live Infura/Web3 node-provider API key into the container's stdout logger. By the project's own topology (`tech-stack.md`, `aws-resources.md`), ECS task logs flow to CloudWatch (`/apps/dm-chain-explorer`, `/ecs/dm-chain-explorer`) and are then shipped via the app-logs **Firehose → S3 lakehouse (`raw/app_logs/`) → Databricks gold pipeline**. So the secret is durably persisted at rest in S3 and queryable in Databricks. Anyone with read access to CloudWatch, the lakehouse bucket, or the Databricks `b_app_logs`/gold tables can recover live provider keys.
- **Relation to prior review:** The streaming-jobs review (backlog SEC-HARD-10 / code-reviewer D-01) flagged only a `key[-4:]` *tail* leak at `etherscan_multi.py:115`. **It did not catch these three full-key cleartext leaks** in `4_mined_txs_crawler.py`. This is a NEW, higher-severity finding.
- **Fix recommendation:** Never log raw key material. Replace `{actual_api_key}` with a non-reversible reference (e.g. the key's logical name from the key manager, or `sha256(key)[:8]`, or a fixed `"<infura-key>"` sentinel). Audit the existing CloudWatch log group and lakehouse `raw/app_logs/` prefix for already-leaked keys and rotate any exposed Infura keys. (Do not implement here — reported only.)

#### H-02 — Long-lived static AWS access keys instead of OIDC, including on PR-triggered plan
- **CWE:** CWE-798 (Use of Hard-coded / Long-Lived Credentials) + CWE-522 (Insufficiently Protected Credentials)
- **OWASP:** A07:2021 Identification & Authentication Failures
- **Severity:** HIGH
- **Location (every `configure-aws-credentials` use across the workflows):**
  - `.github/workflows/deploy_all_dm_applications.yml` — lines 118-119, 236-237, 285-286, 301-302, 445-446, 526-527, 572-573, 637-638, 703-704, 761-762, 802-803, 866-867, 932-933
  - `.github/workflows/deploy_cloud_infra.yml:90`
  - `.github/workflows/plan_on_pr.yml:103-104, 130-131, 157+` (and on through the file)
  - same pattern in `destroy_cloud_infra.yml`, `destroy_all_cloud_infra.yml`, `drift_detection.yml`
- **Evidence (redacted):**
  ```yaml
  aws-access-key-id:     ${{ secrets.AWS_ACCESS_KEY_ID }}      # [REDACTED]
  aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}  # [REDACTED]
  ```
  No workflow uses `role-to-assume` or requests an `id-token` OIDC token (confirmed: zero matches for `role-to-assume`/`id-token` in `.github/workflows/`).
- **Description:** Every AWS-touching job authenticates with a single long-lived IAM access-key pair stored as repo secrets. These credentials do not rotate automatically, have a large blast radius (they drive deploy + destroy of all infra across dev/hml/prd), and are a prime exfiltration target. The risk is amplified because `plan_on_pr.yml` is triggered by `pull_request` (`branches: [develop]`) and injects the **same** static keys — any workflow change or compromised dependency on a PR branch runs with full deploy-capable credentials. (Note: the trigger is `pull_request`, not `pull_request_target`, so a fork PR's malicious YAML would not normally run with secrets unless the fork-PR-secrets setting is enabled — but same-repo branch PRs DO get the secrets.)
- **Fix recommendation:** Migrate to GitHub OIDC: configure an IAM role with a trust policy scoped to this repo/refs, add `permissions: id-token: write`, and replace the static-key inputs with `role-to-assume`. Until then: scope the IAM user minimally per workflow, rotate the keys, and remove AWS credentials entirely from `plan_on_pr.yml` (a plan on an untrusted PR should not hold deploy keys — use a read-only role or run plan without remote state access).

### MEDIUM

#### M-01 — Kinesis Data Streams created with `encryption_type = "NONE"`
- **CWE:** CWE-311 (Missing Encryption of Sensitive Data) | **OWASP:** A02:2021
- **Severity:** MEDIUM
- **Location:** `services/prd/04_peripherals/peripherals.tf:98`; default in `services/modules/kinesis/variables.tf:38` (`optional(string, "NONE")`).
- **Evidence:** `encryption_type = "NONE"` for `mainnet-transactions-data`; module default is `"NONE"`.
- **Description:** On-chain transaction data transits Kinesis unencrypted at rest. Ethereum tx data is public, but stream-level SSE is a cheap defense-in-depth and an expected baseline; the `NONE` default also means any future stream inherits no encryption.
- **Fix recommendation:** Set `encryption_type = "KMS"` with a CMK (or `alias/aws/kinesis`); flip the module default to `"KMS"`.

#### M-02 — SQS queues have no server-side encryption
- **CWE:** CWE-311 | **OWASP:** A02:2021
- **Severity:** MEDIUM
- **Location:** `services/modules/sqs/main.tf:32-65` (`aws_sqs_queue.dlq` and `aws_sqs_queue.this` — no `sqs_managed_sse_enabled` / `kms_master_key_id`).
- **Evidence:** Neither queue resource sets any SSE attribute; messages carry block/tx hash payloads.
- **Fix recommendation:** Add `sqs_managed_sse_enabled = true` (free SSE-SQS) or `kms_master_key_id` to both queue resources.

#### M-03 — Databricks bootstrap token persisted in Terraform state
- **CWE:** CWE-312 (Cleartext Storage of Sensitive Information) | **OWASP:** A02:2021
- **Severity:** MEDIUM
- **Location:**
  - `services/prd/05_databricks/outputs.tf:9-12` (`databricks_token`, `sensitive = true`)
  - `services/prd/05a_databricks_account/outputs.tf:9-10`
  - `services/hml/05_databricks/outputs.tf:9-10` (`token_value`)
  - generated by `databricks_mws_workspaces.dm.token[0].token_value` (`services/prd/05_databricks/databricks.tf:89`, `services/hml/05_databricks/databricks.tf:119`)
- **Evidence:** Workspace admin token is surfaced as a root-module output. `sensitive = true` only suppresses CLI display; the value is still written **in cleartext into the S3 state object**. Value redacted: `[REDACTED]`.
- **Mitigations present:** state bucket `dm-chain-explorer-terraform-state` is SSE-AES256 (`services/prd/01_tf_state/bucket.tf:20-26`), public-access-blocked (`:32-33`), versioned, and DynamoDB-locked; `encrypt = true` in every backend block. This keeps the finding at MEDIUM rather than HIGH.
- **Residual risk:** any IAM principal with `s3:GetObject` on the state bucket (or read on the state via remote_state) can recover a live Databricks admin token; SSE is AWS-managed AES256, not a scoped CMK, so it is not an additional access-control boundary.
- **Fix recommendation:** Avoid exporting the token as an output where possible; if cross-stack consumption is required, store it in Secrets Manager / SSM SecureString and pass the reference, and restrict `s3:GetObject` on the state bucket to the deploy role only (least privilege). Rotate the bootstrap token periodically.

#### M-04 — DynamoDB / Firehose-to-S3 rely on AWS-owned keys (no CMK)
- **CWE:** CWE-311 | **OWASP:** A02:2021
- **Severity:** MEDIUM
- **Location:** `services/modules/dynamodb/main.tf:32-34` (`server_side_encryption { enabled = true }` with no `kms_key_arn` → AWS-owned key); `services/modules/kinesis/main.tf:145-155, 224-234` (`extended_s3_configuration` has no `kms_key_arn` / no `cloudwatch_logging_options` encryption — relies on destination-bucket default AES256).
- **Description:** Encryption is present but uses AWS-owned/managed keys without a customer-managed CMK, so there is no key-policy-level access boundary, no key rotation control, and no CloudTrail key-usage audit. Acceptable for low-sensitivity public chain data, but below a hardened baseline for prd.
- **Fix recommendation:** Where data sensitivity warrants, switch DynamoDB to `KMS` with a CMK and set a CMK on Firehose `extended_s3_configuration`.

#### M-05 — `plan_on_pr.yml` runs Terraform on untrusted PR content with cloud credentials
- **CWE:** CWE-829 (Inclusion of Functionality from Untrusted Control Sphere) | **OWASP:** A08:2021 Software & Data Integrity Failures
- **Severity:** MEDIUM (overlaps H-02; tracked separately for the PR-trigger dimension)
- **Location:** `.github/workflows/plan_on_pr.yml` — `on: pull_request` (lines under `on:`), credentials at `:101-105` etc., `paths: services/**, scripts/ci/**`.
- **Description:** A `pull_request`-triggered job checks out and runs Terraform (`init`/`plan`) on PR-controlled `services/**` and `scripts/ci/**` while AWS credentials are configured in the job environment. Although `pull_request` (not `pull_request_target`) means fork PRs do not receive secrets by default, same-repo branch PRs do, and `terraform plan` can execute provider/`external`/`local-exec`-style data sources from attacker-modified config. The interpolated `github.event.pull_request.number` (`:112` etc.) is an integer, so direct shell injection risk via that token is low.
- **Fix recommendation:** Remove deploy credentials from the PR plan job (use a read-only role, or `terraform plan` with `-refresh=false` and no backend creds), require approval for first-time contributors, and avoid running provider plugins that can execute code from PR-modified config.

### LOW

#### L-01 — SQS IP-allowlist queue policy uses `Principal = "*"` with `Effect: Allow`
- **CWE:** CWE-732 (Incorrect Permission Assignment) | **OWASP:** A01:2021
- **Severity:** LOW
- **Location:** `services/modules/sqs/main.tf:71-99` (`aws_sqs_queue_policy.ip_restrict`).
- **Evidence:** `Principal = "*"`, `Effect = "Allow"`, gated only by `Condition.IpAddress { aws:SourceIp = var.ip_allowlist }`.
- **Description:** Allow-to-`*` resource policies are fragile (any principal from the listed IPs is allowed) and only created when `ip_allowlist` is non-empty (described as DEV-only). Not used in the prd peripherals config reviewed, but the pattern is risky if reused.
- **Fix recommendation:** Prefer an explicit account/role principal plus the IP condition, or invert to a `Deny`-unless-allowlisted policy.

#### L-02 — ECR repositories use `MUTABLE` image tags + `force_delete = true`
- **CWE:** CWE-494 (Download of Code Without Integrity Check) | **OWASP:** A08:2021
- **Severity:** LOW
- **Location:** `services/prd/07_ecs/ecs.tf:359-381` (`onchain-stream-txs`, `onchain-batch-txs`), and `services/modules/ecs/main.tf:35-47` (driven by var).
- **Description:** Mutable tags allow a deployed image tag to be silently overwritten (supply-chain / rollback-tampering risk); `force_delete = true` permits deletion of a non-empty repo. `scan_on_push = true` is correctly set (good).
- **Fix recommendation:** Set `image_tag_mutability = "IMMUTABLE"` for prd repos and pin task-definition images by digest.

#### L-03 — ECS task definitions lack hardening (no `readonlyRootFilesystem`, no `no-new-privileges`, runs as root)
- **CWE:** CWE-250 (Execution with Unnecessary Privileges) | **OWASP:** A05:2021
- **Severity:** LOW
- **Location:** `services/prd/07_ecs/ecs.tf:62-234` (all five task definitions); root-user / unpinned base already tracked as backlog **SEC-HARD-08 (F-08)** at `apps/docker/.../Dockerfile:4`.
- **Description:** No `linuxParameters`/`no-new-privileges`, no `readonlyRootFilesystem`, no `user` override. Tasks run with default (root) container user. Consistent with — and extends — the deferred backlog item F-08 to the Terraform task-definition layer.
- **Fix recommendation:** Add `linuxParameters { initProcessEnabled, capabilities drop ALL }`, `readonlyRootFilesystem = true` (with a writable `/tmp` mount for `ABI_CACHE_DIR`), and a non-root container user.

#### L-04 — ECS tasks in public subnet with `assign_public_ip = true`
- **CWE:** CWE-668 (Exposure of Resource to Wrong Sphere) | **OWASP:** A05:2021
- **Severity:** LOW (mitigated)
- **Location:** `services/prd/07_ecs/ecs.tf:49-55` (`assign_public_ip = true`, public subnet, no NAT GW); SG `services/prd/02_vpc/network.tf:97-117`.
- **Description:** Fargate tasks receive public IPs. **Mitigation:** the `ecs_tasks` security group ingress is restricted to `var.cidr_vpc` only (no `0.0.0.0/0` ingress); egress is open (`0.0.0.0/0`), which is normal for outbound RPC/API calls. Exposure is therefore limited, but a public IP is unnecessary attack surface given the S3 gateway endpoint already exists.
- **Fix recommendation:** Move tasks to private subnets with a NAT/interface endpoints, or keep public-IP only where outbound internet is genuinely required and confirm no service ports are opened on the SG.

#### L-05 — `.gitguardian.yml` ignore-paths create a secret-scanning blind spot
- **CWE:** CWE-1108 (Excessive Reliance on Global Variables — config blind spot) / process gap | **OWASP:** A05:2021
- **Severity:** LOW
- **Location:** `.gitguardian.yml` (ignores `services/{dev,prd}/compose/{app_services,airflow_services}.yml`).
- **Description:** The four ignored compose paths are currently **gitignored / not tracked** (verified — `git ls-files` returns nothing for them), and the documented rationale (SSM pointers, not secrets) is correct for the values seen. The risk is forward-looking: if any of those paths ever becomes tracked, GitGuardian will silently skip it, hiding a real secret. The ignore is a path-level (not value-level) suppression.
- **Fix recommendation:** Narrow the ignore to specific known-safe matches if possible, or rely on the `.gitignore` exclusion alone and drop the scanner ignore so any accidental tracking is still scanned.

### INFO

#### I-01 — No OIDC / federated identity anywhere (tracked under H-02)
Informational restatement: the entire CI surface depends on one static IAM key pair; adopting OIDC removes the standing secret.

#### I-02 — Destroy workflows have confirmation guardrails (positive observation)
`destroy_all_cloud_infra.yml:49-54` requires literal `DESTROY ALL`; `destroy_cloud_infra.yml` requires `DESTROY`; both are `workflow_dispatch`-only and use GitHub `environment:` gates (`environment: dev/hml/prd`), enabling required-reviewer protection. No action required; ensure the environments actually have required reviewers configured in repo settings.

#### I-03 — Third-party Actions are fully SHA-pinned (positive observation)
All `aws-actions/configure-aws-credentials`, `hashicorp/setup-terraform`, `docker/build-push-action`, `databricks/setup-cli`, `actions/checkout` references are pinned to 40-char commit SHAs with a version comment. This is the recommended supply-chain posture; no unpinned `@vN`/`@main` tags found.

---

## Secrets detected

**No live secret values are committed to tracked files.**

| Check | Result |
|---|---|
| Tracked `.env` / `.tfvars` / `.tfstate` / `.pem` / `.key` / `*_credentials.json` | None tracked (`git ls-files` empty for these patterns). |
| Hardcoded `password=`/`secret=`/`token=`/`api_key=` literals | None in tracked non-spec source. |
| Blockchain provider keys (Alchemy/Infura/Etherscan) | No raw keys committed — all references are SSM parameter pointers (`/web3-api-keys/...`, `/etherscan-api-keys`), Databricks table/column names, or vendor literals. |
| Private keys (`BEGIN ... PRIVATE KEY`) | None found. |
| `.gitignore` coverage | Comprehensive: `**/.env`, `**/*.env`, `**/*.tfvars.local`, `**/secrets.tfvars`, `*.key`, `*_credentials.json`, `**/*.secrets.conf`, `**/terraform.tfstate*`. |

> The only secret-exposure issue is **runtime** leakage, not committed secrets: see **H-01** (raw keys logged to CloudWatch/lakehouse) and **M-03** (Databricks token in TF state). Both write secrets to a runtime/storage location, not to git.

---

## CVE findings

**Not run — status unconfirmed.** No local virtualenv is available and this review does not install packages or run scanners against the project. Dependency CVE posture is therefore **unverified** for:
- `apps/docker/onchain-stream-txs/requirements.txt` (`web3>=7.8.0`, `boto3`, `eth-abi`, `requests`, `aiohttp`, `dm-chain-utils>=0.2.9`, etc.)
- Lambda deps and `dm-chain-utils` (`utils/`).

This matches deferred backlog **SEC-HARD-09 (F-09)** and **OI-1** (add `pip-audit` to the CI pre-push gate). Per the prior streaming review note, no known-vulnerable version floors were identified by static inspection as of its review date, but that is not a substitute for a real scan. **Recommendation:** add `pip-audit` to CI (OI-1) and run it for the streaming image, Lambda, and `dm-chain-utils` before relying on a clean CVE result.

---

## IaC findings (summary index)

| Finding | Sev | File:line | Issue |
|---|---|---|---|
| M-01 | MEDIUM | `services/prd/04_peripherals/peripherals.tf:98`; `modules/kinesis/variables.tf:38` | Kinesis `encryption_type = NONE` |
| M-02 | MEDIUM | `services/modules/sqs/main.tf:32-65` | SQS no SSE |
| M-03 | MEDIUM | `services/prd/05_databricks/outputs.tf:9`; hml/05a equivalents | Databricks token in TF state |
| M-04 | MEDIUM | `services/modules/dynamodb/main.tf:32`; `modules/kinesis/main.tf:145,224` | AWS-owned keys, no CMK |
| M-05 | MEDIUM | `.github/workflows/plan_on_pr.yml` | TF plan on PR content with cloud creds |
| L-01 | LOW | `services/modules/sqs/main.tf:71-99` | `Principal="*"` allow + IP condition |
| L-02 | LOW | `services/prd/07_ecs/ecs.tf:359-381` | ECR MUTABLE tags + force_delete |
| L-03 | LOW | `services/prd/07_ecs/ecs.tf:62-234` | Task defs unhardened / root |
| L-04 | LOW | `services/prd/07_ecs/ecs.tf:49-55` | Public-IP Fargate (SG-mitigated) |
| L-05 | LOW | `.gitguardian.yml` | Scanner ignore blind spot |

**Positive IaC observations:** S3 module (`modules/s3/main.tf`) sets `block_public_acls/block_public_policy/ignore_public_acls/restrict_public_buckets = true`, AES256 SSE, versioning, and `prevent_destroy`. The tf_state bucket (`prd/01_tf_state/bucket.tf`) is encrypted + PAB + versioned + DynamoDB-locked with `encrypt = true` backends. IAM module (`modules/iam/main.tf`) is resource-scoped (ARN-constrained per service), the Databricks cross-account trust uses `sts:ExternalId`, and Lambda/ECS task roles are least-privilege per resource — **no wildcard `Action:"*"` or `Resource:"*"` on data-plane roles** (the only `Resource = "*"` is on read-only `ec2:Describe*` for Databricks VPC validation, which is the documented Databricks requirement). VPC SG ingress is VPC-local only.

---

## Cross-reference with existing bugs / backlog (no duplication)

- **`specs/backlog/streaming-jobs-security-hardening.md`** (CANDIDATE, not picked) covers F-04..F-10, SEC-HARD-04..10, TEST-HARD-01/02. **This review does not re-file those.** It specifically distinguishes:
  - **H-01 is NOT a duplicate** of SEC-HARD-10/D-01. SEC-HARD-10 is the `key[-4:]` *tail* leak at `etherscan_multi.py:115`. H-01 is the **full raw key** leak at `4_mined_txs_crawler.py:66/107/114`, which the prior review did not flag and which is HIGH (full secret, propagates to the durable log lakehouse).
  - F-08 (Dockerfile root/unpinned base) is acknowledged; **L-03 extends** it to the Terraform ECS task-definition layer (a different file the backlog item did not cover).
  - SEC-HARD-09 / OI-1 (pip-audit) is acknowledged in the CVE section; not re-filed.
- **`specs/bugs/`** contains no security-prefixed bugs; the existing bugs are drift/best-practice (`bp-01`, `drift-01..10`) and unrelated to this audit's scope.

**Net-new findings this review adds beyond the backlog:** H-01 (full-key log leak), H-02/M-05 (static AWS keys + PR-plan creds), M-01..M-04 (Kinesis/SQS/state/CMK encryption), L-01/L-02/L-04/L-05 (SQS policy, ECR mutability, public-IP Fargate, scanner blind spot).

---

## Open items (need operator decision)

1. **OI-A (H-01 cleanup):** Has the live CloudWatch `/apps/dm-chain-explorer` log group or the `raw/app_logs/` S3 prefix already captured raw Infura keys? If yes, the exposed keys must be **rotated** and historical log objects purged. Decision: rotate now vs. after the log statements are fixed.
2. **OI-B (H-02):** Approve migration to GitHub OIDC for AWS auth (removes the standing static key). Until done, decide whether to immediately strip AWS credentials from `plan_on_pr.yml`.
3. **OI-C (M-03):** Decide whether the Databricks token must remain a cross-stack output; if so, route via Secrets Manager/SSM and tighten `s3:GetObject` on the state bucket to the deploy role only.
4. **OI-D (CVE):** Approve adding `pip-audit` to the CI pre-push gate (pairs with backlog OI-1 / SEC-HARD-09) so the CVE result moves from "unverified" to "confirmed".
5. **OI-E (encryption baseline):** Decide whether prd warrants CMK-backed encryption (M-01/M-02/M-04) or whether AWS-managed keys are acceptable given the data is public chain data.

> No fixes were written. This report is advisory; remediation is performed by the implementing agent under SDD, not by security-reviewer.
