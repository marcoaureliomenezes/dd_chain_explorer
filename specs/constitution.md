---
specs_pattern_version: 5
---

# Project Constitution — dd-chain-explorer

> The immutable laws of this repository. They hold for every change, forever.
> When code and the constitution disagree, the code is corrected — never the constitution.

## 1. What this product is — three repositories, one boundary

The product is segregated into exactly **three** repositories. Nothing lives in two of
them, and no fourth repository is introduced without amending this article.

| Repository | Single concern | Contents |
|---|---|---|
| `dd-chain-infrastructure` | All infrastructure, for all three environments | Terraform root stacks (`dev`, `hml`, `prd`) plus shared modules, and the infrastructure control plane (`.github/workflows/`, `scripts/ci/`) that plans and applies them |
| `dd-chain-explorer` | The application surface and the **main repository of the spec context** | `specs/` (authoritative), `apps/dabs/` (Databricks Asset Bundles — DLT pipelines, jobs, dashboards), `apps/lambda/` (the Python 3.12 Lambdas), `utils/` (the `dm-chain-utils` shared library), `docs/`, `tests/`, and its own application CI |
| `dd-chain-capture` | Blockchain capture | The capture applications that land raw blockchain data. Unchanged by this segregation |

**The two seams, and only these two.** Repositories meet at S3 boundaries, never at a
runtime call, a stream, a queue, or a shared code path:

1. **The capture seam — the S3 raw bucket.** `dd-chain-capture` writes it; this product
   reads it. No second integration surface may be introduced between them.
2. **The lambda seam — the S3 artifacts bucket.** `dd-chain-explorer` CI builds and
   publishes the Lambda layer and handler zips to content-addressed keys;
   `dd-chain-infrastructure` Terraform resolves them by key and digest. Neither repository
   reads the other's working tree.

Both seams are pinned by one document — `docs/cross-repo-contract.md` in
`dd-chain-explorer` — which states the bucket, prefix and key shapes, the OIDC role map,
and the Databricks split (workspace infrastructure is Terraform-by-import in the
infrastructure repository; DLT pipelines, workflows and dashboards are DABs in the
explorer). A seam changed in code but not in that document is a defect.

**`specs/` is authoritative in `dd-chain-explorer`.** Once the v0.6.0 cutover lands, the
`specs/` tree of the new `dd-chain-explorer` repository is the single source of SDD truth
for all three repositories — constitution, memory, releases, backlog, bugs and audits.
Until that cutover commit, this legacy tree is the live one; after it, the legacy tree is
frozen and no SDD artifact is ever written there again. Neither
`dd-chain-infrastructure` nor `dd-chain-capture` carries its own `specs/` tree.

## 2. Environments

| Environment | Meaning |
|---|---|
| `dev` | Development. Full lane; deployable from CI and locally. |
| `hml` | Homologation. Deliberately **minimal** — it validates the deploy path, not production parity. |
| `prd` | Production. Applied only through CI, behind an approval gate. |

There is exactly **one Databricks workspace**, Free Edition, serverless compute only,
serving the `dev` and `hml` targets. No production Databricks workspace exists; the
`prod` bundle target is not deployable and stays guarded.

## 3. Principles

1. **`dd-chain-explorer` is public, and declares no infrastructure.** It is PUBLIC from
   birth, so only public-grade content may be committed: no personal identifiers, e-mail
   addresses, secrets, cloud account ids, hostnames, or machine-local absolute paths
   anywhere in the tree — source, specs, evidence, or commit messages; evidence uses
   generic resource names. It declares **no** infrastructure: no Terraform, no
   `services/` directory, no cloud-mutating workflow, and no deploy role beyond the
   single artifacts-publish role of the lambda seam. Infrastructure belongs to
   `dd-chain-infrastructure`, capture to `dd-chain-capture`. The same public-grade bar
   applies to `dd-chain-infrastructure` once it is made public.
2. **Secrets never live in the tree.** Runtime reads them from SSM Parameter Store; CI
   reads them from the repository secret store. Only `*.example` files are committed.
3. **CI authenticates by OIDC only.** No static cloud keys in any workflow. The trust
   anchor and the deploy roles live in a **bootstrap stack applied by the operator**,
   outside the CI-applied path; a CI-applied stack must never be able to grant or mutate
   its own permissions.
4. **One version axis: the SDD release id** under `specs/releases/`. No second numbering
   scheme, no independent artifact version, no tag family that drifts from it.
5. **No tracked binaries.** Zips, layers, wheels and images are built and published by
   CI from source; they are never committed.
6. **Every test declares its intent and its size at birth.** An undeclared test is
   scaffold and expires. A test is deleted, skipped or quarantined only on a
   `qa-engineer` verdict carrying evidence — never to make a run go green.
7. **Memory is current truth.** `specs/memory/**` describes the product as it is now;
   history lives in `CLOSURE.md` and `specs/_archive/`. No changelog in memory.
8. **Infrastructure changes only through CI applying Terraform.** Terraform, in
   `dd-chain-infrastructure`, is the only source of truth for infrastructure, and the CI
   pipeline is the only actor that applies it: a resource is never created, modified or
   destroyed by a console click or an ad-hoc CLI mutation. The **sole** exception is
   `services/prd/00_bootstrap` — the trust anchor that mints the CI roles, and therefore
   cannot be applied by them (the bootstrap paradox); it is applied by the operator, never
   by CI. A mutation outside CI and outside that one exception is a defect to register,
   not a shortcut.
9. **Branch law**, no fifth pattern: `main` (never committed or pushed to directly;
   advances only by PR from `develop`), `develop` (the only pushable branch),
   `feature/{M.m.p}` and `hotfix/{M.m.p}` (local only, cut from `develop`).
10. **One audit, one remediation release.** Every finding of an audit receives an
    explicit disposition in that release — fixed, superseded, or deferred/rejected with a
    reason. An audit is archived only once fully dispositioned, naming the release.

## 4. Security non-negotiables

1. Never hardcode API keys, tokens, passwords or connection strings in any file.
2. Never commit `*.tfstate`, `*.tfstate.backup`, `secrets.tfvars`, or a `.env` with real
   values.
3. Never embed cloud access keys in code, containers or workflow files.
4. Runtime API keys are read from SSM at execution time; the runtime receives only the
   parameter path.
5. IAM is least privilege: no `s3:*`, no `iam:*`, every resource scoped by ARN and by
   environment.
6. S3 buckets: all four public-access blocks `true`, encryption enabled, versioning
   enabled.
7. Secrets, key material and identifiers are never printed to logs, job summaries,
   reports or specs — including key tails and partial values.

## 5. Terraform rules

These rules govern `dd-chain-infrastructure`, the only repository that declares
infrastructure (§1, §3.8).

- Remote state, always; never apply with `-lock=false`.
- Plan before apply — in CI the plan is produced, gated and only then applied.
- Provider and Terraform versions are pinned; lock files are committed.
- Every resource carries the common tags: `owner`, `managed-by`, `cost-center`,
  `environment`, `project`.
- Naming: `dm-{env}-` or `dm-dd-chain-explorer-{env}-`.
- Sensitive values live in gitignored `*.tfvars`; only `*.tfvars.example` is committed.
- A stack's inter-stack inputs come from declared outputs or documented state keys —
  never from a copy-pasted literal.

## 6. Databricks and DABs rules

- Never use `path=` in `@dlt.table` / `@dlt.view` — Unity Catalog forbids explicit paths.
- Catalogs, buckets, warehouse and cluster references come from bundle variables
  (`${var.*}`); nothing is hardcoded per target.
- Auto Loader reads `s3://{bucket}/raw/{prefix}/`. `bronze` is a schema name, never an
  S3 prefix.
- **No bundle references another bundle's resource.** Each bundle is self-contained;
  a pipeline's trigger job lives in the pipeline's own bundle.
- Deployed state equals repository state. The workspace is split at one line: Unity
  Catalog **workspace infrastructure** — storage credentials, external locations and
  catalogs — is declared by Terraform in `dd-chain-infrastructure` and adopted by import,
  never created ad hoc; everything above it — DLT pipelines, workflows, jobs and
  dashboards — is a DAB in `dd-chain-explorer`. An asset that is neither Terraform-declared
  nor in a bundle does not belong in the workspace.

## 7. Data conventions

**S3 layout**

- Streaming landing: `s3://{raw-bucket}/raw/{source}/year=YYYY/month=MM/day=DD/hour=HH/`
- Batch output: `s3://{raw-bucket}/raw/batch/{dataset}/year=YYYY/month=MM/day=DD/`
- Gold exports: `s3://{lakehouse-bucket}/exports/`

**DynamoDB** — one table with `pk` + `sk` and an entity prefix per record type; the live
entities are `CONTRACT` (contract metadata) and `CONSUMPTION` (gold export). A new
entity type is added to memory in the same release that introduces it.

**Medallion naming**

| Pipeline | Bronze | Silver | Gold |
|---|---|---|---|
| Ethereum | `b_ethereum` | `s_apps` | `gold`, `g_network` |
| Application logs | `b_app_logs` | `s_logs` | `g_api_keys` |

Silver and Gold never share a schema.

## 8. Python rules

- PEP 8, enforced by the linter; type hints on every public function and method.
- Imports at the top of the file, grouped stdlib → third-party → local.
- The shared library is imported by its distribution name (`dm_chain_utils.<module>`),
  never by a relative or vendored path.
- No bare `print()` in production code — use structured logging.

## 9. Commit format

```
<type>(<scope>): <short summary>
```

Types: `feat`, `fix`, `chore`, `infra`, `ci`, `docs`, `refactor`, `test`.
Scopes: `dlt`, `dabs`, `lambda`, `terraform`, `ci`, `specs`, `deps`.

## 10. Data classification

| Data type | Classification | Basis |
|---|---|---|
| Wallet addresses | Pseudo-anonymous public data | Legitimate interest — public blockchain data |
| Transaction hashes, block numbers, timestamps | Non-PII technical data | Not personal data |
| Application and function logs | Non-PII by default | Must never contain key material |

No column masking is required for the current assets. If identity-linked addresses are
ever introduced, those columns are reclassified as sensitive personal data and masked
before landing in Silver or Gold. This classification is reviewed by every release that
adds a data source or an entity type.
