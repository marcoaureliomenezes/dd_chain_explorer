# Spec: Domínio — DevOps

> **Status:** Implementado
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/constitution.md`, `specs/memory/architecture.md`

---

## Escopo

Toda a estratégia de CI/CD e gestão do ciclo de vida do código:
- **7 workflows GitHub Actions** (`.github/workflows/`)
- **16 scripts CI** (`scripts/ci/`)
- **GitFlow** e política de branches
- **Versionamento** semântico via arquivo `VERSION`

Este domínio NÃO inclui: código de aplicação, Terraform, DABs.

---

## GitFlow

```
master  ←── release/{scope}-v{VERSION}  (criado automaticamente pelo CI)
  └── develop  ←── feature/*  |  hotfix/*  (todos os PRs)
```

- `master` e `develop` são protegidas — **nunca push direto**
- Todo deploy é `workflow_dispatch` a partir de `develop`
- `branch_guard.sh` enforça essa regra em todos os workflows

---

## Workflows

| Workflow | Trigger | Propósito |
|----------|---------|-----------|
| `auto-bump-version.yml` | Push pós-merge em `develop` | Incrementa `VERSION`, cria commit |
| `plan_on_pr.yml` | PR → `develop` | Terraform plan nos módulos alterados (sem apply) |
| `deploy_cloud_infra.yml` | `workflow_dispatch` | Terraform apply: DEV, HML ou PRD |
| `deploy_all_dm_applications.yml` | `workflow_dispatch` | Pipeline completo: streaming + DABs + Lambda |
| `drift_detection.yml` | Schedule + manual | Terraform plan PRD; alerta em drift |
| `destroy_cloud_infra.yml` | `workflow_dispatch` | Destroy seletivo por ambiente |
| `destroy_all_cloud_infra.yml` | `workflow_dispatch` | Destroy total com gate "DESTROY" |

### Pipeline de Aplicações — Estágios Completos

```
CHECK
  └── BUILD (parallel)
        ├── streaming image (ECR)
        ├── Lambda ZIPs
        └── DABs bundles
            └── HML DEPLOY
                  ├── ECS tasks efêmeros
                  ├── DABs (Free Edition)
                  └── Lambda
                      └── HML TEST
                            ├── streaming integration tests
                            └── DLT gold validation
                                └── HML TEARDOWN (always — mesmo em falha)
                                      └── PRD DEPLOY (approval gate "production")
                                            └── PRD TAG (v{VER}, v{VER}-dabs, v{VER}-lambda)
```

**HML é 100% efêmero.** `hml_teardown` roda no bloco `if: always()` — sem exceção.

---

## Scripts CI (`scripts/ci/`)

| Script | Propósito |
|--------|-----------|
| `branch_guard.sh` | Valida branch = `develop` — falha o job se não |
| `bump_version.sh` | Incrementa VERSION (patch/minor/major) |
| `check_prd_version.sh` | Verifica que tag `v{VER}-infra` não existe ainda |
| `check_commit_confirmation.sh` | Exige string "DESTROY" para destruições |
| `detect_changes.sh` | Detecta quais módulos DEV mudaram via `git diff` |
| `hml_provision.sh` | Cria SG efêmero HML com tag `GITHUB_RUN_ID` |
| `hml_teardown.sh` | Remove SG efêmero + ECS tasks HML |
| `tf_plan.sh` | Wrapper Terraform plan com output formatado |
| `tf_state_lock_check.sh` | Remove locks DynamoDB obsoletos |
| `wait_eni_release.sh` | Aguarda ENIs liberados após scale-down de ECS |
| `deploy_env.sh` | Orquestra deploy sequencial por ambiente (HML/PRD) |
| `databricks_account_import.sh` | Import idempotente de recursos Databricks account-level |
| `empty_s3_and_ecr.sh` | Esvazia S3 e ECR antes de destroy |

---

## Versionamento

`VERSION` na raiz do repo é a única fonte de verdade. **Nunca bumpar manualmente antes de deploy.**

| Evento | Tag criada | Por |
|--------|-----------|-----|
| Deploy streaming | `v{VERSION}` | `deploy_all_dm_applications` |
| Deploy DABs | `v{VERSION}-dabs` | `deploy_all_dm_applications` |
| Deploy Lambda | `v{VERSION}-lambda` | `deploy_all_dm_applications` |
| Deploy infra | `v{VERSION}-infra` | `deploy_cloud_infra` |
| Release library | `v{VERSION}-lib` | Manual |

---

## Requisitos Funcionais

**FR-DO-001 — Branch guard universal**
Todo workflow de deploy deve rodar `branch_guard.sh` como primeiro step. Workflows disparados de qualquer branch diferente de `develop` devem falhar imediatamente.

**FR-DO-002 — PRD com approval gate**
Todo deploy em PRD deve passar pelo GitHub Environment `production` — nunca deploy automático em PRD.

**FR-DO-003 — HML teardown garantido**
O step `HML TEARDOWN` deve estar em bloco `if: always()`. Recursos HML efêmeros nunca devem sobrar após um run (com ou sem falha).

**FR-DO-004 — Secrets via GitHub Secrets**
Nenhum secret pode ser hardcoded em arquivos YAML de workflow. Sempre `${{ secrets.SECRET_NAME }}`.

**FR-DO-005 — Lógica em scripts**
Toda lógica de workflow com mais de 10 linhas de shell deve estar em `scripts/ci/` — nunca inline no YAML.

**FR-DO-006 — Commit format**
Commits devem seguir: `<type>(<scope>): <summary>`. Tipos válidos: `feat`, `fix`, `chore`, `infra`, `ci`, `docs`, `refactor`. Scopes: `stream`, `batch`, `dlt`, `dabs`, `ecs`, `lambda`, `terraform`, `deps`.

**FR-DO-007 — Drift detection**
O workflow `drift_detection.yml` deve rodar em schedule e reportar qualquer drift Terraform PRD via GitHub Actions Summary.

---

## Requisitos Não-Funcionais

- **NFR-DO-001:** O pipeline completo de aplicações (CHECK → PRD TAG) deve completar em < 45 minutos em condições normais.
- **NFR-DO-002:** Nenhum workflow deve ter secrets visíveis em logs — usar `add-mask` para outputs sensíveis.
- **NFR-DO-003:** `terraform_wrapper: false` sempre — para preservar exit codes corretamente no CI.

---

## Fora de Escopo (v1)

- Deploy automático em PRD sem approval gate
- Múltiplos ambientes PRD (multi-region)
- Rollback automatizado em caso de falha PRD
