---
specs_pattern_version: 5
---

# Project Constitution — dd-chain-explorer

> The immutable laws of this repository. They hold for every change, forever.
> When code and the constitution disagree, the code is corrected — never the constitution.

## 1. What this repository is

Three surfaces, one repository:

| Surface | Path | Contents |
|---|---|---|
| Infrastructure | `services/` | Terraform stacks per environment plus shared modules |
| Control plane | `.github/workflows/`, `scripts/ci/` | GitHub Actions workflows and their helper scripts |
| Data artifacts | `apps/dabs/`, `apps/lambda/` | Databricks Asset Bundles (DLT pipelines, jobs, dashboards) and two Python 3.12 Lambdas |

Blockchain **capture is not in this repository**. It belongs to the external
`dd-chain-capture` project. The two projects meet at exactly one place: the **S3 raw
bucket**. No second integration surface — no stream, no queue, no shared runtime, no
direct call — may be introduced between them.

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

1. **The repository is public.** No personal identifiers, e-mail addresses, secrets,
   cloud account ids, or machine-local absolute paths anywhere in the tree — source,
   specs, evidence, or commit messages. Evidence uses generic resource names.
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
8. **Terraform is the only source of truth for infrastructure.** Never create, modify or
   destroy a resource from the console or by ad-hoc CLI call.
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
- Deployed state equals repository state: an asset that is not in a bundle does not
  belong in the workspace.

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
