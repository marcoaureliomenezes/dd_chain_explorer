# GitHub CI/CD – dd_chain_explorer

This document describes the GitFlow strategy, GitHub Actions workflows, required secrets, and branch protection rules for the `dd_chain_explorer` project.

---

## GitFlow

```
main
 └── release/x.y.z     ← RC branch; merged into main + develop after release
       └── develop      ← integration branch; all feature/fix PRs target here
             ├── feature/<short-description>
             ├── fix/<short-description>
             └── chore/<short-description>
```

| Branch pattern | Purpose | Direct push |
|---|---|---|
| `main` | Production-ready code only | ❌ PRs only |
| `develop` | Integration of finished features | ❌ PRs only |
| `release/*` | Release candidates | ❌ PRs only |
| `feature/*` | New features | ✅ author only |
| `fix/*` | Bug fixes | ✅ author only |
| `chore/*` | Maintenance / deps | ✅ author only |
| `infra/*` | Infrastructure changes | ✅ author only |

### Commit message convention

```
<type>(<scope>): <short summary>

feat(stream): add broker pre-warm on producer init
fix(batch): handle empty Etherscan response
chore(deps): bump confluent-kafka to 2.5.0
infra(ecs): add ECR repositories to Terraform
ci(deploy): migrate DockerHub → ECR
docs(readme): update GitFlow section
```

---

## Workflows

| Workflow | File | Trigger |
|---|---|---|
| **CI – dm-chain-utils** | `ci_lib.yml` | push/PR on `utils/**` |
| **Deploy Apps** | `deploy_apps.yml` | push to `master` on `docker/**` or `utils/**` |
| **CI – Terraform Plan** | `ci_terraform_plan.yml` | PR on `services/prd/terraform/**` |
