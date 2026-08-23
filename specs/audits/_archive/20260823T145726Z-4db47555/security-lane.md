# Security Review — dd-chain-explorer (AUDIT LANE, full scan)

- **Date (UTC):** 2026-08-23
- **Reviewer:** security-reviewer
- **Repo:** `repos/dd-chain-explorer`
- **Branch / commit reviewed:** `feature/v0.4.0` @ `c6feb17` (*chore(specs): migrate specs tree to pattern version 5*)
- **Lane:** **AUDIT** (`project-auditor` dispatch class) — full-repo scan. **This is NOT a push-gate verdict** and authorizes no push. The pre-push security-verdict chokepoint requires a separate diff-based review of `origin/develop..develop`.
- **Posture:** static, read-only. No exploit code, no fuzzing, no network scanners, **no live AWS/Databricks calls, no `gh api` calls**. All secret-like values redacted to first 4 chars + `****`.
- **Prior artifacts consumed:**
  - `specs/audits/20260611T001412Z-cb56f84c/security-review.md`
  - `.dadaia/handoff/dd-chain-explorer/2026-06-11T001412Z-security-reviewer-full-audit.handoff.json`
  - `.dadaia/handoff/dd-chain-explorer/2026-06-23T000518Z-security-reviewer-v040-capture-retirement.handoff.json`

> **Disclaimer.** Point-in-time snapshot. No codebase is ever "fully secure". Section 8 lists everything this pass did **not** reach.

---

## 1. Scan summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 6 |
| LOW | 12 |
| INFO | 6 |

**Tools / passes actually executed**

| Pass | Tool / method | Result |
|---|---|---|
| Working-tree secret scan | `git grep -nIE` over tracked files (AWS keys, `dapi*`, PEM headers, generic `k=v` credential literals, 32-hex, 34-char uppercase) | 0 real hits |
| Git-history secret scan | custom blob walker over **6,530** objects / **542** commits (`git rev-list --all --objects` + `git cat-file`), 2 pattern passes, Python redactor | 0 live credentials; 4 legacy artefacts (L9) |
| Dependency CVE (manifests) | `pip-audit 2.10.1` on 3 `requirements.txt` + `utils/pyproject.toml` deps | clean at latest-resolution (misleading — see M6) |
| Dependency CVE (deployed artifact) | `pip-audit --no-deps` on the 46 pinned versions extracted from the **committed** `dm_chain_utils_layer.zip` | **31 vulns / 4 packages** |
| SAST | `bandit 1.9.4 -r apps utils scripts` (199 results) | 4 MEDIUM, rest LOW (181 = `assert_used` in tests) |
| Supply chain | public PyPI existence probe for `dm-chain-utils` / `dm_chain_utils` | **HTTP 404 — name unclaimed** |
| IaC review | targeted read of `services/**` (IAM, OIDC, S3, VPC/SG, Lambda, DynamoDB, ECR/ECS, tf_state, Databricks) | see §5 |
| CI review | all 7 workflows: triggers, `permissions:`, action pinning, credential model, OIDC subjects | see §4 |
| DABs review | 12 `databricks.yml` bundles + `resources/**` grants/permissions/run_as | see §6 |

**Headline.** The v0.3.0 OIDC cutover fully retired static AWS keys (prior **H-02 closed**) and the v0.4.0 capture retirement obsoleted 5 prior findings. The dominant risk has shifted from *credential handling* to **supply-chain and artifact provenance**: an unclaimed PyPI name is pinned in three production manifests, the deployed Lambda-layer binary is committed to git, diverges from its own CI-enforced pin, and carries 31 known CVEs. Separately, the three CI deploy roles hold `PowerUserAccess` + `iam:*`-class actions on `Resource: "*"`, a documented-but-live privilege-escalation path to account admin.

**Correction to the prior audit (material).** Prior **H-01** ("raw Web3/Infura API key logged in cleartext → rotate keys") was a **misclassification**. `actual_api_key` is the **SSM parameter *name*** (e.g. `infura-api-key-1`), never the key value: `Web3Handler.get_node_connection(api_key_name)` resolves the secret via `ParameterStoreClient.get_parameter(name, WithDecryption=True)` and has done so since the file's *only* commit (`2f2b45f`, 2026-03-16) — i.e. also at the time of the 2026-06-11 audit. **No live Infura key was ever written to CloudWatch or the log lakehouse by that code path.** Open item **OI-A** (emergency Infura rotation + historical log purge) is therefore **not justified by the cited evidence**. Details: §3 and finding L2.

---

## 2. Findings table

| id | CWE | Sev | Area | Finding | Evidence (`file:line`, redacted) | Recommendation |
|---|---|---|---|---|---|---|
| **H1** | CWE-1357 / CWE-829 | **HIGH** | Supply chain | **Dependency confusion.** `dm-chain-utils==0.2.9` is pinned in 3 production manifests and installed by `pip install -r requirements.txt` against the **default public index** (no `--index-url`, no `--extra-index-url`, no hash pinning). The name is **unclaimed on public PyPI** (`GET https://pypi.org/pypi/dm-chain-utils/json` → **404**; underscore spelling → **404**). Anyone may register it and publish `0.2.9`; the next stream-image build then installs attacker code into a runtime holding the ECS task role (SSM `web3-api-keys/*` + `etherscan-api-keys/*`, DynamoDB, S3). Today the build **fails closed** on the 404 — luck, not a control. The Lambda **layer** is safe (built from local source: `pip install --target … "${UTILS_DIR}/"`). | `apps/docker/onchain-stream-txs/requirements.txt:4`; `apps/lambda/contracts_ingestion/requirements.txt:4`; `apps/lambda/gold_to_dynamodb/requirements.txt:4`; `apps/docker/onchain-stream-txs/Dockerfile:9-11`; `.github/workflows/deploy_all_dm_applications.yml:143-148` (image build) | Remove `dm-chain-utils` from every `requirements.txt` and install it the way the layer already does (local path / built wheel). If it must stay a requirement, publish/claim the name **or** pin `--index-url` to a private index plus `--require-hashes`. Defensively register the name on PyPI. |
| **H2** | CWE-269 / CWE-732 | **HIGH** | IAM / CI | **CI deploy roles can escalate to account admin.** All three OIDC deploy roles attach AWS-managed `PowerUserAccess` **plus** an inline statement granting `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy`, `iam:UpdateAssumeRolePolicy`, `iam:PassRole` on `resources = ["*"]`. Any actor able to run a deploy in `environment:dev` (memory records dev as the auto-approved, reviewer-less environment) can attach `AdministratorAccess` to any role or rewrite any trust policy. Acknowledged in-file as a bootstrap trade-off deferred to backlog epic WS-D — but it is live. | `services/prd/03_iam/oidc.tf:156-184` (`IamManagement`, `resources = ["*"]`), `:217-232` (dev role), `:234-249` (hml), `:251-266` (prd); comment `:145-152` | Scope `IamManagement` to `arn:aws:iam::<acct>:role/dm-chain-explorer-*` and drop `PowerUserAccess` for per-service statements. At minimum add an `iam:PermissionsBoundary` condition and a `Deny` on `iam:*` against roles outside the project prefix. Require reviewers on `environment:dev` while the wildcard stands. |
| **H3** | CWE-1104 / CWE-937 | **HIGH** | Dependencies / integrity | **The deployed Lambda-layer artifact is committed, stale, vulnerable, and contradicts its own CI gate.** `services/prd/06_lambda/.lambda_zip/dm_chain_utils_layer.zip` (37 MB, tracked since 2026-03-21) is what Terraform ships. It contains **`dm_chain_utils-0.1.0`** — while the CI step *"Validate dm-chain-utils exact pin in all production artifacts"* asserts `==0.2.9` **by grepping text files only**, never the artifact. `pip-audit` on the 46 pinned versions inside it: **31 known vulnerabilities in 4 packages** (see §4b). It also ships `redis-7.3.0`, a dependency no current manifest declares (pre-DynamoDB leftover). | `services/prd/06_lambda/.lambda_zip/dm_chain_utils_layer.zip` (`python/lib/python3.12/site-packages/dm_chain_utils-0.1.0.dist-info`); `.github/workflows/deploy_all_dm_applications.yml:88-104` (text-only pin gate) | Stop committing build artifacts; build the layer in CI and publish by digest. Rebuild the layer now from `utils/` @ 0.2.9. Extend the pin gate to verify the **artifact's** `dist-info` version, not a grep of `requirements.txt`. Raise floors: `aiohttp>=3.14.3`, `urllib3>=2.7.0`, `requests>=2.33.0`, `idna>=3.15`. |
| **M1** | CWE-732 / CWE-522 | MEDIUM | IAM / OIDC | **Read-only plan role trusts the broadest PR subject.** `gha_readonly_plan` trusts `sub = repo:<org>/<repo>:pull_request` — *any* PR from *any* branch, no environment claim — and attaches AWS-managed **`ReadOnlyAccess`** (account-wide `s3:GetObject`, `dynamodb:GetItem`, `ssm:GetParameter`, …). Chained with **M2**, a PR author can read `s3://<tf-state-bucket>/…` and recover the **Databricks workspace admin token in cleartext**. (Fork PRs are blocked by GitHub's read-only-token rule for `pull_request`; same-repo branch PRs are not.) | `services/prd/03_iam/oidc.tf:116-143` (`values = [… ":pull_request", ":ref:refs/heads/…"]`), `:301-316` (`ReadOnlyAccess` attach + state-bucket read) | Replace `ReadOnlyAccess` with a plan-scoped policy (state read + `Describe*/Get*` on the managed services only). Narrow the `sub` to `repo:<org>/<repo>:pull_request` **plus** a `token.actions.githubusercontent.com:environment` or head-ref condition, or move PR plans behind an environment. Explicitly `Deny` `s3:GetObject` on the state bucket for this role once M2 is fixed. |
| **M2** | CWE-312 | MEDIUM | IaC / secrets | **Databricks bootstrap token persisted in Terraform state (unchanged since 2026-06-11).** `databricks_mws_workspaces.dm.token[0].token_value` is exported as a root-module output; `sensitive = true` suppresses CLI display only — the value is written **cleartext into the S3 state object**. Mitigated (not removed) by SSE-AES256 + PAB + versioning + DynamoDB lock on the state bucket. Value redacted: `[REDACTED]`. | `services/prd/05_databricks/outputs.tf:9-12`; `services/prd/05a_databricks_account/outputs.tf:9-12`; `services/hml/05_databricks/outputs.tf:9-12` | Drop the output, or route the token through Secrets Manager / SSM SecureString and pass only the reference. Restrict `s3:GetObject` on the state bucket to the deploy roles. Rotate the bootstrap token. |
| **M3** | CWE-494 / CWE-829 | MEDIUM | CI | **Unpinned remote script executed in a `pull_request`-triggered job.** `bash <(curl -fsSL …/actionlint/main/scripts/download-actionlint.bash)` fetches from a moving `main` ref with no checksum/SRI and pipes it to `bash`. Every other third-party action in the repo is 40-char SHA-pinned — this is the one hole in an otherwise strong pinning posture. | `.github/workflows/plan_on_pr.yml:69-72` | Use the SHA-pinned `rhysd/actionlint` action, or vendor the installer and verify a checksum before executing. |
| **M4** | CWE-732 / CWE-1188 | MEDIUM | IAM | **Dead grants to retired services survive with resurrect-by-name wildcards.** v0.4.0 destroyed Kinesis/Firehose/SQS, but the surviving prd ECS task role still grants `KinesisAccess`, `FirehoseAccess`, `SQSAccess` scoped by **name pattern**, not by concrete ARN. Any future stream/queue matching `mainnet-*-prd` / `firehose-mainnet-*-prd` silently inherits full data-plane access. | `services/prd/03_iam/iam.tf:57-67` (Kinesis), `:72-77` (Firehose), `:82-92` (SQS); module vars `services/modules/iam/variables.tf:36-42` | Delete the three statements as part of capture-retirement closure; keep the module variables only if the module is still consumed elsewhere. |
| **M5** | CWE-494 | MEDIUM | Supply chain | **Five binary deployment artifacts are committed and are Terraform's source of truth.** Consumed by `archive_file`/`filename` in the Lambda stacks; never scanned, not reproducible from source, and drifting (see H3). Handler zips carry a forged mtime (`2049-01-01`). | `services/prd/06_lambda/.lambda_zip/{dm_chain_utils_layer,contracts_ingestion,gold_to_dynamodb}.zip`; `services/dev/02_lambda/.lambda_zip/gold_to_dynamodb.zip`; `services/modules/cloudwatch_logs/.lambda_zip/cw_logs_transform.zip` | Build in CI, publish to S3 by digest, reference the object version from Terraform. Gitignore `.lambda_zip/`. |
| **M6** | CWE-1104 | MEDIUM | Dependencies | **`>=`-only floors make the CVE scan a false negative.** Every manifest uses unbounded `>=`, and the floors are *exactly* the vulnerable versions (`aiohttp>=3.13.3`, `urllib3>=2.6.3`, `requests>=2.32.4`). `pip-audit` on the manifests resolves to latest and reports **"No known vulnerabilities found"**, while the artifact actually deployed is vulnerable. A CI gate built on the manifests would stay green forever. | `apps/docker/onchain-stream-txs/requirements.txt:1,7,8`; evidence `pip_audit2.out` (clean) vs `pip_audit_layer.json` (31 vulns) | Adopt a lockfile (`pip-compile` + `--require-hashes`) and run `pip-audit` against the **lock/artifact**, not the manifest. Add it to the deploy gate (closes prior OI-D / SEC-HARD-09). |
| **L1** | CWE-532 | LOW | Secrets (runtime) | **Etherscan key tail leak still open** (prior SEC-HARD-10 / code-reviewer D-01, unremediated). Fallback logs the last 4 chars of a **live** Etherscan key when the key→name map misses. | `apps/docker/onchain-stream-txs/src/utils_decode/etherscan_multi.py:115` — `…key {self._key_names.get(key, key[-4:])}` | Replace the fallback with `_key_ref()`-style `sha256(key)[:8]` or a fixed sentinel. |
| **L2** | CWE-497 | LOW | Logging | **Key-namespace enumeration in the shared library.** `APIKeysManager` logs the full list of SSM parameter names at init and the elected name per rotation. These are **names, not secrets** (see §3), but they flow to CloudWatch → app-logs Firehose → S3 → Databricks gold, durably publishing the SSM key namespace to every lakehouse reader. The crawler was already fixed to `_key_ref()`; the library underneath was not. | `utils/src/dm_chain_utils/api_keys_manager.py:26` (`API KEYS: {self.api_keys}`), `:84` (`API KEY ELECTED: {api_key}`), `:64`; cf. fixed `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py:12-21,79,120,127` | Log an index or `_key_ref()` digest instead of the parameter name; drop the init-time full-list dump. |
| **L3** | CWE-269 | LOW | Secrets handling | **Latent bulk-decryption helper.** `ParameterStoreClient.list_parameters()` paginates every SSM parameter in the account and calls `get_parameters(..., WithDecryption=True)`, returning a `{name: cleartext}` dict. **No caller exists today** — a loaded gun in a shared library. | `utils/src/dm_chain_utils/dm_parameter_store.py:51-75` | Delete it, or require an explicit path prefix argument and never return values for paths outside it. |
| **L4** | CWE-1104 / CWE-250 | LOW | Container | **Dockerfile unhardened** (prior SEC-HARD-08 / F-08, still open): floating `python:3.12-slim` tag with no digest pin, no `USER` directive (runs as **root**), no `--no-cache-dir`, no `--require-hashes`. | `apps/docker/onchain-stream-txs/Dockerfile:4,10-11` | Pin `FROM python:3.12-slim@sha256:…`, add a non-root `USER`, `pip install --no-cache-dir --require-hashes`. |
| **L5** | CWE-494 | LOW | IaC | **ECR still `MUTABLE` + `force_delete = true`** (prior L-02, unchanged). A deployed tag can be silently overwritten; a non-empty repo can be deleted. `scan_on_push = true` is correctly set. | `services/prd/07_ecs/ecs.tf:60-70` (`onchain-stream-txs`), `:72-82` (`onchain-batch-txs`) | `image_tag_mutability = "IMMUTABLE"`; reference task-definition images by digest. |
| **L6** | CWE-359 / CWE-522 | LOW | Databricks / privacy | **Operator's personal email hardcoded as `run_as.user_name` in all 12 DABs prod targets.** PII committed to the repo, and prod jobs run under a **human identity** rather than a service principal — no separation of duties, and every job dies with the account. | `apps/dabs/job_ddl_setup/databricks.yml:44-45`; identical in `alert_api_keys`, `alert_dynamodb_deadlock`, `dashboard_{api_health,gas_analytics,hot_contracts,network_overview}`, `genie_ethereum`, `job_{delta_maintenance,export_gold,full_refresh,reconcile_orphans,trigger_all}` | Move `run_as` to a Databricks service principal; parameterise via a bundle variable fed from a secret. |
| **L7** | CWE-200 | LOW | Databricks / disclosure | **Databricks workspace host hardcoded in 12 bundles** (dev + hml targets): `https://dbc-409f****.cloud.databricks.com`. Not a credential, but a concrete internal infra identifier in the tree. The **prod** target correctly uses `host: ""` injected from `secrets.DATABRICKS_PROD_HOST` — the right pattern, applied inconsistently. | `apps/dabs/*/databricks.yml` (e.g. `job_ddl_setup/databricks.yml:26,36` vs `:47`) | Apply the prod pattern to dev/hml: empty host + variable from CI. |
| **L8** | CWE-668 | LOW | Network | **Security-group ingress is all-protocol / all-port from the entire VPC CIDR** (`protocol = "-1"`, ports 0-0 → all). Egress `0.0.0.0/0` is normal for outbound RPC; there is **no** `0.0.0.0/0` ingress anywhere. Blast radius is currently nil (ECS services destroyed in v0.4.0) but the SG definitions survive. | `services/prd/02_vpc/network.tf:97-117`; `services/modules/vpc/main.tf:82-100` | Narrow ingress to the ports actually needed, or drop the ingress rule entirely for egress-only tasks. |
| **L9** | CWE-312 / CWE-530 | LOW | Secrets (history) | **Legacy `.env` files and a demo secret persist in git history** (all deleted from HEAD, all from the pre-v0.1 Airflow/Spark tree). Contents inspected and redacted: local dev-compose credentials only — `PG_AIRFLOW_PASSWORD=****(len 7)`, `PG_NESSIE_PASSWORD=****(len 6)`, `POSTGRES_PASSWORD=****(len 7)`, Hive `ConnectionPassword=****(len 4)` — plus internal Kafka broker hostnames (`KAFKA_BROKERS_PROD=brok****(len 44)`) and the Hue documentation default `secret_key=kasd****`. **No cloud or provider credential.** Risk is disclosure-on-publication, given this repo's prior infra-leak-driven open-source revert. | history blobs: `services/{app,compose,data_lake,fast,swarm,transactional}/.env`, `services/.env`, `services/data_lake/conf/hadoop-hive.env`, `docker/{customized,batch_layer}/hue/hue.ini:7` | Rotate the (local-only) compose passwords if any survive in a running stack. Treat the repo as permanently private, **or** rewrite history before any publication. |
| **L10** | CWE-89 | LOW | Injection | **SQL built by f-string interpolation** (`bandit` B608 ×2 in tracked source). Interpolated values are a job parameter (`args.catalog`) and module constants — not end-user input — so exploitation requires job-definition write access. Defence-in-depth only. | `apps/dabs/job_ddl_setup/src/dd_chain_explorer/check/check_tables.py:97`; `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py:527` | Validate `--catalog` against an allowlist / `^[A-Za-z0-9_]+$` before interpolation. |
| **L11** | CWE-377 | LOW | Filesystem | Hardcoded temp path `/tmp/abi_cache` (env-overridable) used as an ABI disk cache (`bandit` B108, MEDIUM/MEDIUM). Low risk on Fargate/Lambda's private `/tmp`. | `utils/src/dm_chain_utils/dm_etherscan.py:45` | Use `tempfile.mkdtemp()` or keep the env override but assert a non-world-writable owner. |
| **L12** | CWE-390 / CWE-778 | LOW | Logging | **Silent exception swallowing** (`try/except: pass`, `bandit` B110 ×3) — a failed 4byte lookup, a failed CloudWatch emit, and an Etherscan path fail invisibly. A09: security-relevant failures leave no audit trail. | `apps/docker/onchain-stream-txs/src/utils_decode/etherscan_multi.py:154`; `utils/src/dm_chain_utils/dm_cloudwatch_logger.py:201`; `utils/src/dm_chain_utils/dm_etherscan.py:257` | Log at `debug`/`warning` with the exception type instead of `pass`. |
| **I1** | — | INFO | CI | **Static AWS keys fully eliminated.** Zero matches for `aws-access-key-id` / `AWS_SECRET_ACCESS_KEY` across `.github/` and `scripts/`; 30 `role-to-assume` uses across 4 workflows. Prior **H-02 closed**. | `grep -rn 'aws-access-key-id\|AWS_SECRET_ACCESS_KEY' .github/ scripts/` → empty | No action. |
| **I2** | — | INFO | CI | **No `pull_request_target` anywhere**; every workflow declares a least-privilege top-level `permissions:` block (`contents: read` + `id-token: write`, with `contents: write` narrowed to the two jobs that tag/bump). | `.github/workflows/*.yml` (`auto-bump-version:9`, `deploy_all_dm_applications:23`, `deploy_cloud_infra:35`, `destroy_all_cloud_infra:25`, `destroy_cloud_infra:24`, `drift_detection:17`, `plan_on_pr:22`) | No action. |
| **I3** | — | INFO | Supply chain | **All third-party Actions SHA-pinned** to 40-char commits with version comments (`checkout`, `setup-terraform`, `setup-python`, `configure-aws-credentials`, `docker/build-push-action`, `upload-artifact`, `databricks/setup-cli`). Sole exception is M3. | e.g. `plan_on_pr.yml:47-48` | No action. |
| **I4** | — | INFO | IaC | **S3 hardening is correct.** The module sets `block_public_acls`/`block_public_policy`/`ignore_public_acls`/`restrict_public_buckets = true`, AES256 SSE, versioning, `prevent_destroy`. State bucket likewise SSE + PAB + versioned + DynamoDB-locked. | `services/modules/s3/main.tf:10-30`; `services/prd/01_tf_state/bucket.tf:20-33` | No action. |
| **I5** | — | INFO | IaC | **Lambda environment variables carry no secrets** — only SSM/bucket/table *pointers* (`SSM_ETHERSCAN_PATH = "/etherscan-api-keys"`, `S3_BUCKET`, `DYNAMODB_TABLE`). Secrets resolve at runtime through `ParameterStoreClient`. | `services/prd/06_lambda/lambda_contracts_ingestion.tf:113-119`; `lambda.tf:83-85` | No action. |
| **I6** | — | INFO | Secrets | **Working tree is clean.** Zero AWS key IDs, zero PEM private-key headers, zero `dapi`-prefixed Databricks PATs, zero credential literals in tracked non-spec source. The one 32-hex literal is a synthetic test fixture (`abcdef0123456789deadbeefcafef00d`). `.gitignore` coverage for `.env`/`tfvars`/`tfstate`/`*.pem`/`*.key` is comprehensive. | `apps/docker/onchain-stream-txs/tests/unit/test_4_mined_txs_crawler.py:242`; `.gitignore` | No action. |

---

## 3. Secrets detected

**Working tree: none. Git history: no live credential.**

| Check | Scope | Result |
|---|---|---|
| AWS access-key IDs (`AKIA`/`ASIA`/`AIDA`/`AROA` + 16) | tree + 6,530 history blobs | **0** |
| Databricks PAT (`dapi` + 32 hex) | tree + history | **0** |
| Private keys (`BEGIN … PRIVATE KEY`) | tree + history | **0** |
| Infura/Alchemy URL-embedded keys (`infura.io/v3/…`, `alchemy.com/v2/…`) | tree + history | **0** |
| Generic `password|secret|token|api_key = "…"` literals | tree (excl. specs/docs) | **0** |
| Tracked `.env` / `*.tfvars` / `*.tfstate` / `*.pem` / `*.key` | tree | **0** |
| Historical `.env` blobs | history | **8 paths, local dev-compose only** → L9 |
| `secrets.tfvars.example` | history | placeholder `"<SER****"` — safe by design |
| `scripts/setup_github_secrets.sh` | history | reads from `aws configure export-credentials` / `read -rsp`; **no embedded values** |
| All `AWS_SECRET_ACCESS_KEY` history hits | history | every one is `os.getenv("AWS_****")` — env reads, not literals |

### The Infura question, answered

> *"the 2026-06-11 audit found an Infura key logged in history; confirm whether it was rotated/purged (still in history yes/no)"*

**Not in history — and it never was.** Two independent facts:

1. **It was never a git-history finding.** Prior H-01 described a *runtime* log-emission path (code → CloudWatch → Firehose → S3 → Databricks), not a committed value. The prior audit's own Secrets section states *"No live secret values are committed to tracked files."* This pass's 6,530-blob history walk confirms it independently: **zero** matches for any Infura/Alchemy key shape anywhere in history.
2. **The logged value was never the key.** `elect_new_api_key()` returns an SSM **parameter name**; `Web3Handler.get_node_connection(api_key_name)` is what resolves it to a secret via `get_parameter(..., WithDecryption=True)`. Verified across the file's entire history — `dm_web3_client.py` has exactly **one** commit (`2f2b45f`, 2026-03-16), predating the 2026-06-11 audit, and that version already takes the name.

**Conclusion:** `[REDACTED]` Infura key material — **not in history (no)**, not in the tree, and not written to CloudWatch by the cited lines. **OI-A is closed as not-applicable.** The code was nonetheless hardened (`_key_ref()` = `sha256(key)[:8]`) at `4_mined_txs_crawler.py:12-21`, which is correct defensive practice; the equivalent hardening is still missing one layer down (**L2**).

---

## 4. CVE findings

### 4a. Manifests (latest-resolution) — CLEAN, and misleading

| Manifest | pip-audit | Note |
|---|---|---|
| `apps/docker/onchain-stream-txs/requirements.txt` | No known vulnerabilities | resolves to latest, not to what is deployed (**M6**) |
| `apps/lambda/contracts_ingestion/requirements.txt` | No known vulnerabilities | idem |
| `apps/lambda/gold_to_dynamodb/requirements.txt` | No known vulnerabilities | idem |
| `utils/pyproject.toml` (deps) | No known vulnerabilities | idem |

> All four runs initially **failed** with `Could not find a version that satisfies the requirement dm-chain-utils==0.2.9 (from versions: none)` — the raw signal behind **H1**. Re-run with that line removed.

### 4b. The artifact actually deployed — 31 vulnerabilities / 4 packages

Extracted from the 46 `*.dist-info` entries inside the committed `dm_chain_utils_layer.zip`.

| Package | Installed | Advisories | Representative CVEs | Fix |
|---|---|---|---|---|
| **aiohttp** | **3.13.3** | **25** | CVE-2026-69243 (WebSocket **request smuggling**), CVE-2026-69244 (heap OOB read in C parser), CVE-2026-34520 (null bytes / control chars accepted in request line), CVE-2026-59881 (RSV1 decompression w/o `permessage-deflate`), CVE-2026-54275/54276/54277/54278/54279/54280, CVE-2026-34513/34514/34515/34516/34517/34518/34519/34525, CVE-2026-47265, CVE-2026-50269, CVE-2026-34993, CVE-2026-22815 | **3.14.3** |
| **urllib3** | **2.6.3** | 3 | CVE-2026-44431 (cross-origin redirect handling), CVE-2026-44432 (streaming API) | **2.7.0** |
| **idna** | **3.11** | 1 | CVE-2026-45409 (incomplete fix for CVE-2024-3651 — DoS on crafted payloads) | **3.15** |
| **requests** | **2.32.5** | 1 | CVE-2026-25645 (`requests.utils.extract_zipped_paths()`) | **2.33.0** |

**Affected code path.** The layer is attached to `dm-chain-explorer-gold-to-dynamodb` and `dm-chain-explorer-contracts-ingestion` (prd + dev). `requests`/`urllib3`/`idna` are on the live path (`contracts_ingestion` → Etherscan API, hourly EventBridge). `aiohttp` is used by the *stream* jobs, currently retired — most aiohttp advisories are **server-side**, so the practical exposure through the Lambda layer is limited to client-side parsing; **CVE-2026-44431/44432 (urllib3)** and **CVE-2026-25645 (requests)** are the actionable ones. Severity scores were not fetched (offline advisory metadata only carries IDs/fix versions) — **CVSS is unverified**, so none of these met the CVSS ≥ 9.0 escalation trigger on evidence; H3's HIGH rating rests on artifact-integrity + volume, not on a confirmed critical score.

**No dependency CVE met the "CVSS ≥ 9.0 in a production dependency" escalation threshold on available evidence.**

### 4c. Base images

| Image | Pinning | Finding |
|---|---|---|
| `python:3.12-slim` | floating tag, **no digest** | **L4** |

---

## 5. IaC findings (index)

| id | Sev | `file:line` | Issue |
|---|---|---|---|
| H2 | HIGH | `services/prd/03_iam/oidc.tf:156-184,217-266` | `PowerUserAccess` + `iam:*`-class on `Resource "*"` → account-admin escalation |
| M1 | MEDIUM | `services/prd/03_iam/oidc.tf:116-143,301-316` | `:pull_request` OIDC subject + `ReadOnlyAccess` → state-bucket read |
| M2 | MEDIUM | `services/prd/05_databricks/outputs.tf:9`; `05a/outputs.tf:9`; `hml/05_databricks/outputs.tf:9` | Databricks admin token cleartext in S3 state |
| M4 | MEDIUM | `services/prd/03_iam/iam.tf:57-92` | Dead Kinesis/Firehose/SQS grants with name-pattern wildcards |
| M5 | MEDIUM | `services/{prd/06_lambda,dev/02_lambda,modules/cloudwatch_logs}/.lambda_zip/*.zip` | Committed binary deploy artifacts as TF source of truth |
| L5 | LOW | `services/prd/07_ecs/ecs.tf:60-82` | ECR `MUTABLE` + `force_delete = true` |
| L8 | LOW | `services/prd/02_vpc/network.tf:97-117`; `services/modules/vpc/main.tf:82-100` | SG ingress all-protocol/all-port from whole VPC CIDR |
| I4 | INFO | `services/modules/s3/main.tf:10-30`; `services/prd/01_tf_state/bucket.tf:20-33` | S3 + state backend correctly hardened |
| I5 | INFO | `services/prd/06_lambda/lambda*.tf` | No secrets in Lambda env vars — SSM pointers only |

**KMS posture.** No customer-managed keys anywhere: S3 = SSE-AES256, DynamoDB = `server_side_encryption { enabled = true }` with no `kms_key_arn` (AWS-owned key). Acceptable for public chain data; below a hardened prd baseline. Carried forward from prior M-04 (partial — see §7). `kms:Decrypt` is granted only where SSM SecureString / Secrets Manager reads require it (`services/prd/03_iam/iam.tf:31`, `services/modules/iam/main.tf:34`).

**Public access / open CIDRs.** Four `0.0.0.0/0` occurrences, **all egress**; zero public-ingress rules; zero public S3.

---

## 6. Databricks bundle (DABs) findings

| Check | Result |
|---|---|
| Hardcoded tokens / PATs in bundles | **None.** Only reference: `apps/dabs/deploy_all.sh:20` documents `DATABRICKS_TOKEN` as an env var. |
| `permissions:` / `grants:` / `access_control` blocks | **None declared in any bundle** — including `job_ddl_setup`. Resources therefore inherit workspace defaults. **Not a permissive-grant finding; it is an absent-grant finding** — no explicit least-privilege ACL is asserted anywhere, so the effective posture depends entirely on Free-Edition workspace defaults, which this static review cannot read. Recommend adding explicit `permissions:` blocks per job/dashboard. |
| Prod workspace host | `host: ""` + `secrets.DATABRICKS_PROD_HOST` — correct |
| Dev/hml workspace host | hardcoded `https://dbc-409f****…` ×12 → **L7** |
| `run_as` | operator's personal email ×12 → **L6** |
| Secrets in CI for DABs | `DATABRICKS_{ACCOUNT_ID,CLIENT_ID,CLIENT_SECRET}` (OAuth M2M), `DATABRICKS_{HML,PROD}_HOST`, `DATABRICKS_HML_TOKEN` — all via `secrets.*`, none echoed to logs in any reviewed step |
| SQL construction in DLT/job code | 2 f-string sites → **L10** |

---

## 7. Previous findings status

Source: `specs/audits/20260611T001412Z-cb56f84c/security-review.md` (2026-06-11) and the two prior handoffs.

| Prior id | Prior sev | Status **today** | Evidence / reason |
|---|---|---|---|
| **H-01** — raw Infura key logged to CloudWatch/lakehouse | HIGH | **RECLASSIFIED → LOW, and hardened** | **Misclassified at origin.** `actual_api_key` is the SSM *parameter name*; `get_node_connection` resolves the secret from SSM (`dm_web3_client.py:30-41`, unchanged since `2f2b45f`, 2026-03-16 — i.e. also true on 2026-06-11). Code nonetheless hardened to `_key_ref()` = `sha256[:8]` (`4_mined_txs_crawler.py:12-21,79,120,127`). Residual name-logging one layer down → **L2**. **OI-A (rotate Infura keys / purge logs) closed as not-applicable.** |
| **H-02** — static AWS keys incl. on PR-triggered plan | HIGH | **FIXED** | Full OIDC cutover: 4 roles in `services/prd/03_iam/oidc.tf`, 30 `role-to-assume` uses, **zero** `aws-access-key-id` / `AWS_SECRET_ACCESS_KEY` in `.github/` or `scripts/`. New residuals introduced by the cutover: **H2**, **M1**. |
| **M-01** — Kinesis `encryption_type = "NONE"` | MEDIUM | **OBSOLETE** | `services/modules/kinesis/` deleted in v0.4.0; no Kinesis resource remains in `services/`. |
| **M-02** — SQS no server-side encryption | MEDIUM | **OBSOLETE** | `services/modules/sqs/` deleted in v0.4.0. |
| **M-03** — Databricks bootstrap token in TF state | MEDIUM | **STILL OPEN** (unchanged) | `services/prd/05_databricks/outputs.tf:9-12` + 05a + hml identical → **M2**. Now *chains* with **M1** (PR-scoped role can read the state bucket). **OI-C still open.** |
| **M-04** — DynamoDB / Firehose on AWS-owned keys, no CMK | MEDIUM | **PARTIALLY OBSOLETE** | Firehose half obsolete (module deleted). DynamoDB half **still open**: `services/modules/dynamodb/main.tf:32-34` still has no `kms_key_arn`. Not re-filed as a separate finding — folded into §5 KMS posture. **OI-E still open.** |
| **M-05** — `plan_on_pr.yml` runs TF on PR content with cloud creds | MEDIUM | **PARTIALLY FIXED** | Deploy keys removed; job now assumes the dedicated `AWS_DEPLOY_ROLE_READONLY` (`plan_on_pr.yml:143,173,…,393`), and `validate` runs `-backend=false` offline (`:63`). Residual: the role is over-broad → **M1**; PR job still executes an unpinned remote installer → **M3**. **OI-B closed.** |
| **L-01** — SQS `Principal = "*"` + IP condition | LOW | **OBSOLETE** | `services/modules/sqs/` deleted. |
| **L-02** — ECR `MUTABLE` tags + `force_delete = true` | LOW | **STILL OPEN** (unchanged) | `services/prd/07_ecs/ecs.tf:60-82` → **L5**. |
| **L-03** — ECS task defs unhardened / root | LOW | **OBSOLETE (runtime) / partially open (source)** | The five task definitions were removed with the capture retirement; `07_ecs` now declares only cluster + capacity providers + log group + service discovery + 2 ECR repos. The container-level half (root user, unpinned base) survives in the Dockerfile → **L4**. |
| **L-04** — public-IP Fargate tasks | LOW | **OBSOLETE (runtime)** | ECS services destroyed in v0.4.0; SG definitions survive with VPC-local ingress only → **L8**. |
| **L-05** — `.gitguardian.yml` ignore-path blind spot | LOW | **NOT RE-VERIFIED** | Out of this pass's reach — see §8. |
| **CVE section** — "not run, unverified" | — | **NOW RUN** | `pip-audit 2.10.1` executed on 4 manifests + the deployed layer. Result: manifests clean, **artifact 31 vulns** → **H3**, **M6**. **OI-D (add pip-audit to CI) still open and now strongly evidenced.** |
| **SEC-HARD-10 / D-01** — `key[-4:]` tail leak, `etherscan_multi.py` | backlog | **STILL OPEN** | `apps/docker/onchain-stream-txs/src/utils_decode/etherscan_multi.py:115` → **L1**. |
| **SEC-HARD-08 / F-08** — Dockerfile root + unpinned base | backlog | **STILL OPEN** | `apps/docker/onchain-stream-txs/Dockerfile:4` (no digest), no `USER` → **L4**. |
| **v0.4.0 LOW** — `destroy_env.sh` whole-env teardown still targets `module.dynamodb` | LOW | **STILL OPEN** (advisory, unchanged) | `scripts/ci/destroy_env.sh:81` `S3_PRESERVED_TARGETS`; the explicit WARNING block at `:72-81` remains the only mitigation, as accepted in the 2026-06-23 handoff. |
| **v0.4.0 INFO** — IAM blast radius capture-only | INFO | **SUPERSEDED** | The claim ("no survivor loses an IAM control") holds. This pass adds the inverse observation the diff-scoped review could not see: survivors *retained* controls they no longer need → **M4**. |

**Score:** 2 prior HIGH → 1 fixed, 1 reclassified. 5 prior MEDIUM → 2 obsolete, 1 open, 2 partial. 5 prior LOW → 3 obsolete, 1 open, 1 not-re-verified. 2 prior backlog items → both still open. **7 net-new findings** (H1, H2, H3, M1, M3, M4, M5/M6) — of which H2/M1 are consequences of the OIDC cutover and H1/H3/M5/M6 are a supply-chain class the prior audit could not assess (no scanner available then).

---

## 8. NOT COVERED — explicit scope gaps

Everything below was **not** examined. Do not read absence of a finding here as absence of risk.

| # | Area | Why not covered |
|---|---|---|
| 1 | **Live AWS state** — `aws iam get-role/get-role-policy`, `aws ssm describe-parameters`, actual attached policies, OIDC provider thumbprint, whether `PowerUserAccess` is genuinely attached in the account | Permitted by the brief but **not exercised**. The entire IAM/OIDC analysis is **source-only**: it describes what Terraform *declares*, not what is *deployed*. Drift between the two is unmeasured. |
| 2 | **Live GitHub state** — `gh api`: branch protection on `main`/`develop`, required reviewers on the `dev`/`hml`/`hml-apps`/`production` environments, `pr-source-guard` status, fork-PR secret settings, whether repo vars `AWS_DEPLOY_ROLE_*` point at the roles reviewed | Not exercised. **H2's severity partly depends on `environment:dev` having no required reviewers** — asserted from workspace memory, **not verified against the live repo**. Verify before acting on H2's priority. |
| 3 | **`.gitguardian.yml`** (prior L-05) | Not re-read this pass. Prior finding's status is unknown. |
| 4 | **Dedicated IaC scanners** (`checkov`, `tfsec`, `terrascan`) | Not installed, not run. Terraform was reviewed by targeted reading of IAM/OIDC/S3/VPC/Lambda/DynamoDB/ECR/state/Databricks — **not an exhaustive walk of all 101 `services/**` files**. `services/hml/**` was reviewed for IAM only; hml `02_vpc`, `04_peripherals`, `05b`, `07_ecs` were not walked. |
| 5 | **Dedicated secret scanners** (`trufflehog`, `gitleaks`, `detect-secrets`) | **None available on this host** (all four probed, all MISSING). History coverage came from a custom two-pass regex walker over 6,530 blobs + 542 commits with a Python redactor. It has **no entropy heuristic** — a high-entropy secret in an unrecognised format could evade it. Treat §3 as strong-but-not-exhaustive. |
| 6 | **Committed handler zips' contents** | The 4 non-layer zips were listed (`unzip -l`) but their `handler.py` bytes were **not** diffed against `apps/lambda/*/handler.py`. Whether the deployed handler matches source is **unverified** — the same class of drift proven for the layer (H3). |
| 7 | **Lakeview dashboard JSON / Genie space** (`*.lvdash.json`, `genie_ethereum/resources/`) | Not read. Embedded queries, row filters, and any sharing/ACL config inside them are unreviewed. |
| 8 | **CVSS scores** | pip-audit's offline advisory data carries IDs and fix versions only. **No CVSS number in §4b is verified.** The CVSS ≥ 9.0 escalation trigger could not be evaluated on evidence. |
| 9 | **`scripts/ci/*.sh` (18 helpers)** | Only `destroy_env.sh` and `branch_guard.sh` were touched, via prior-finding follow-up. The other 16 shell helpers were **not** reviewed for injection, `eval`, or unquoted expansion. |
| 10 | **Runtime / data-plane** | No Databricks Unity Catalog grants, no S3 bucket policies as-deployed, no CloudWatch log contents, no DynamoDB item inspection. Whether the log lakehouse *already contains* leaked material (the L2 class) is **unknown**. |

---

## 9. Open items — operator decision required

1. **OI-1 (H1, act first).** Decide the `dm-chain-utils` distribution model: local-path install (recommended, matches the layer) vs. private index vs. claiming the name on PyPI. **Until resolved, the name is squattable and the stream-image build is broken.** Defensive PyPI registration costs nothing and closes the window today.
2. **OI-2 (H2).** Verify (via `gh api`) whether `environment:dev` has required reviewers. If not, either add them or scope `IamManagement` immediately — the escalation path is one `workflow_dispatch` away.
3. **OI-3 (H3/M5/M6).** Approve removing `.lambda_zip/**` from git in favour of CI-built, digest-referenced artifacts, and adding `pip-audit` against a lockfile to the deploy gate (this is prior **OI-D**, now evidenced).
4. **OI-4 (M2, = prior OI-C).** Still undecided since 2026-06-11: must the Databricks token remain a cross-stack output? If yes, route via SSM SecureString and restrict `s3:GetObject` on the state bucket to the deploy roles only — which also defuses **M1**.
5. **OI-5 (§8 #1/#2).** Authorise a follow-up **live-state** pass (`aws iam`, `aws ssm describe-parameters`, `gh api`) to confirm that deployed IAM matches the reviewed Terraform. This audit measured intent, not reality.
6. **OI-6 (L9).** Confirm the repo stays permanently private. If publication is ever reconsidered, history rewrite is mandatory (dev-compose passwords + internal Kafka broker hostnames + Databricks workspace host).
7. **OI-7 (prior OI-E, M-04 remnant).** Decide whether prd warrants CMK-backed encryption for DynamoDB, or whether AWS-owned keys remain acceptable for public chain data.

---

## 10. Intake routing (FR6/R4)

- **Actionable → `project-manager` intake report:** H1, H2, H3, M1, M2, M3, M4, M5, M6, L1, L2, L3, L4, L5, L6, L7, L8, L10, L11, L12.
- **Record-only (terminates here, never enters intake):** I1-I6 (positive observations); L9 (history artefacts — no fix surface without a history rewrite, gated on OI-6); the H-01 reclassification (a correction to a closed finding, not new work).

---

*No fixes were written. This report is advisory; remediation is performed by the implementing agent under SDD, never by security-reviewer.*
