# Spec: Domínio — DevOps

> **Status:** Implementado
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/constitution.md`, `specs/memory/architecture.md`

---

## Escopo

Toda a estratégia de CI/CD e gestão do ciclo de vida do código:
- **7 workflows GitHub Actions** (`.github/workflows/`)
- **13 scripts CI** (`scripts/ci/`)
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
| `deploy_dm_applications.yml` | `workflow_dispatch` | Deploy individual por tipo de aplicação (streaming, DABs ou Lambda) |
| `deploy_cloud_infra.yml` | `workflow_dispatch` | Terraform apply: DEV, HML ou PRD |
| `deploy_all_dm_applications.yml` | `workflow_dispatch` | Pipeline completo: streaming + DABs + Lambda |
| `destroy_cloud_infra.yml` | `workflow_dispatch` | Destroy seletivo por ambiente |
| `destroy_all_cloud_infra.yml` | `workflow_dispatch` | Destroy total com gate "DESTROY" |
| `lib_release.yml` | `workflow_dispatch` | Release da library `utils` com tag `v{VERSION}-lib` |

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
| `databricks_account_import.sh` | Import idempotente de recursos Databricks account-level |
| `empty_s3_and_ecr.sh` | Esvazia S3 e ECR antes de destroy |
| `check_app_version.sh` | Lê `VERSION` e valida inexistência de tag para o sufixo alvo |
| `check_infra_prerequisites.sh` | Valida pré-requisitos de infra por tipo de app |
| `validate_env_secret_pair.sh` | Valida pairing de host/token Databricks por ambiente (HML/PRD) |
| `check_all_app_versions.sh` | Valida `VERSION` para tags `v{VERSION}`, `v{VERSION}-dabs`, `v{VERSION}-lambda` |
| `update_ecs_services_image.sh` | Atualiza task definitions ECS com nova image e força rollout |
| `wait_ecs_services_stable.sh` | Aguarda estabilização dos serviços ECS e publica resumo opcional |

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
Drift de Terraform PRD deve ser detectado via execução de `terraform plan` no `deploy_cloud_infra.yml` antes de `apply`, com falha explícita em erro de plano e evidência no summary/log do job.

**FR-DO-008 — Exceções operacionais IaC-only**
Operações destrutivas via AWS CLI fora do state estrito só são permitidas nos workflows versionados de destroy, seguindo `specs/domains/infrastructure/OPERATIONAL-EXCEPTIONS-IAC.md`.

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

---
