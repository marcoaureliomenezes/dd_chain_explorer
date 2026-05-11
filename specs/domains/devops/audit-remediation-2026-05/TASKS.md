# Tasks: Audit Remediation — CI/CD, Infra e Arquitetura

> **Spec:** `specs/domains/devops/audit-remediation-2026-05/SPEC.md`
> **Plan:** `specs/domains/devops/audit-remediation-2026-05/PLAN.md`
> **Status:** Aprovado
> **Data:** 2026-05-11

---

## Regras de Execução

- Atualizar status de cada task de `[ ]` para `[-]` ao iniciar e `[x]` ao concluir.
- Toda mudança em workflow deve incluir evidência de validação (lint + checagem estática).
- Não avançar de fase sem concluir critérios de aceite da fase anterior.

---

## Fase 0 — Bloqueadores PRD

### T0.1 Corrigir secrets Databricks no deploy PRD
- [x] Mapear todos os steps PRD com Databricks em `deploy_dm_applications.yml`.
- [x] Substituir `DATABRICKS_HML_TOKEN` por secret de PRD nos steps PRD.
- [x] Mapear todos os steps PRD com Databricks em `deploy_all_dm_applications.yml`.
- [x] Substituir `DATABRICKS_HML_TOKEN` por secret de PRD nos steps PRD.
- [x] Validar que steps HML continuam usando token HML.

### T0.2 Criar gate de consistência ambiente/secret
- [x] Criar `scripts/ci/validate_env_secret_pair.sh` com `set -euo pipefail`.
- [x] Implementar regra de falha para pairing inválido (`HOST`/token).
- [x] Integrar script nos jobs PRD de `deploy_dm_applications.yml`.
- [x] Integrar script nos jobs PRD de `deploy_all_dm_applications.yml`.
- [x] Adicionar mensagens de erro explícitas para troubleshooting.

### T0.3 Validar fase 0
- [x] Executar validação estática: não há `DATABRICKS_HML_TOKEN` em etapas PRD.
- [x] Executar teste local do script com cenário válido.
- [x] Executar teste local do script com cenário inválido.
- [x] Registrar evidência em resumo de execução.
- Evidências (2026-05-11):
  - PRD DABs deploy jobs usam `DATABRICKS_PROD_TOKEN` em ambos workflows (`deploy_dm_applications.yml`, `deploy_all_dm_applications.yml`).
  - `validate_env_secret_pair.sh` aprovado no cenário válido de PRD.
  - `validate_env_secret_pair.sh` falha corretamente no cenário inválido com `::error::Invalid host/token pairing for PRD`.

---

## Fase 1 — Governança e Confiabilidade

### T1.1 Resolver drift spec x implementação
- [x] Inventariar workflows/scripts reais ativos.
- [x] Escolher estratégia final (A implementar faltantes / B atualizar spec) e registrar decisão no PR.
- [x] Aplicar estratégia escolhida integralmente.
- [x] Revisar `specs/domains/devops/SPEC.md` para aderência 1:1 com estado final.
- Estratégia escolhida: **B** (atualizar spec para refletir estado real atual), com backlog futuro para introduzir `plan_on_pr.yml` e `drift_detection.yml` em spec dedicada.
- Inventário real (2026-05-11):
  - Workflows: `auto-bump-version.yml`, `deploy_all_dm_applications.yml`, `deploy_cloud_infra.yml`, `deploy_dm_applications.yml`, `destroy_all_cloud_infra.yml`, `destroy_cloud_infra.yml`, `lib_release.yml`.
  - Scripts CI: `branch_guard.sh`, `bump_version.sh`, `check_app_version.sh`, `check_commit_confirmation.sh`, `check_infra_prerequisites.sh`, `check_prd_version.sh`, `databricks_account_import.sh`, `detect_changes.sh`, `empty_s3_and_ecr.sh`, `hml_provision.sh`, `hml_teardown.sh`, `tf_plan.sh`, `validate_env_secret_pair.sh`.
- Resultado aplicado na spec de DevOps:
  - Inventário ajustado para 7 workflows e 13 scripts reais.
  - Referências fantasmas removidas (`plan_on_pr.yml`, `drift_detection.yml`, `tf_state_lock_check.sh`, `wait_eni_release.sh`, `deploy_env.sh`).
  - `FR-DO-007` atualizado para refletir o mecanismo de drift atual no `deploy_cloud_infra.yml`.

### T1.2 Extrair shell inline crítico para scripts
- [x] Identificar blocos >10 linhas nos workflows alvo.
- [x] Extrair blocos priorizados para `scripts/ci/`.
- [x] Garantir validação de parâmetros e códigos de saída.
- [x] Substituir blocos inline por chamadas aos scripts.
- [x] Garantir compatibilidade funcional dos jobs afetados.
- Extrações aplicadas (2026-05-11):
  - `scripts/ci/check_all_app_versions.sh` (substitui validação inline de versão em `deploy_all_dm_applications.yml`).
  - `scripts/ci/update_ecs_services_image.sh` (substitui atualização inline de task definitions ECS em `deploy_dm_applications.yml` e `deploy_all_dm_applications.yml`).
  - `scripts/ci/wait_ecs_services_stable.sh` (substitui `aws ecs wait` inline em ambos workflows).
  - `deploy_all_dm_applications.yml` passou a usar `scripts/ci/branch_guard.sh` em vez de bloco inline.
- Evidência técnica:
  - `bash -n` executado com sucesso nos novos scripts.
  - Referências aos scripts confirmadas via `rg` nos workflows alterados.
  - `actionlint` executado com sucesso nos workflows do repositório após refactor.
  - Simulação local validada para `validate_env_secret_pair.sh` (cenário válido e inválido).

### T1.3 Endurecer decisão de state bucket
- [x] Revisar `prevent_destroy` do bucket de state PRD.
- [x] Definir decisão técnica (alterar valor ou manter com controle compensatório).
- [x] Documentar decisão no domínio de infraestrutura/devops.
- [x] Validar que fluxo de destroy continua controlado com confirmação forte.
- Decisão aplicada (2026-05-11):
  - `services/prd/01_tf_state/bucket.tf` alterado para `prevent_destroy = true`.
  - Controle compensatório formalizado em `specs/domains/infrastructure/SPEC.md` (FR-INF-007): deleção do backend de state apenas no fluxo operacional explícito `destroy_all_cloud_infra.yml` com confirmação manual.

### T1.4 Validar fase 1
- [x] Lint de workflows alterados.
- [x] Verificação de sintaxe/execução básica dos scripts novos.
- [x] Revisão manual de aderência FR-DO-005.
- [x] Atualizar relatório de conformidade parcial.
- Evidências (2026-05-11):
  - `actionlint` sem findings.
  - `bash -n` validado para scripts novos e scripts críticos de CI.
  - Workflows `deploy_dm_applications.yml` e `deploy_all_dm_applications.yml` migraram blocos inline críticos para `scripts/ci/`.

---

## Fase 2 — Hardening Estrutural

### T2.1 Reduzir permissões IAM amplas
- [x] Localizar statements IAM com `resources = ["*"]` no escopo da auditoria.
- [x] Propor restrições por ARN/condição sem quebrar integração.
- [x] Aplicar restrições tecnicamente viáveis.
- [x] Documentar exceções remanescentes com risco residual.
- Resultado (2026-05-11):
  - Wildcard identificado em `services/prd/03_iam/iam.tf` (statement EC2 Databricks cross-account).
  - Restrição aplicada por condição regional obrigatória `aws:RequestedRegion = sa-east-1`, reduzindo blast radius.
  - Exceção residual: `resources = ["*"]` mantido por limitação prática do conjunto amplo de ações EC2 usadas no onboarding cross-account Databricks; mitigado por escopo regional fixo.

### T2.2 Formalizar exceções IaC-only
- [x] Criar documento de decisão operacional para uso de AWS CLI em teardown.
- [x] Referenciar decisão nas specs de `devops` e `infrastructure`.
- [x] Criar checklist pós-operação para mitigação de drift.

### T2.3 Validar fase 2
- [-] Executar `terraform validate` nos módulos tocados.
- [x] Revisar impacto em pipelines de deploy/destroy.
- [x] Registrar status de risco residual por item.
- Evidências e bloqueios (2026-05-11):
  - `terraform` não disponível no ambiente local (`terraform: command not found`), validação pendente para execução em runner CI.
  - Impacto de pipeline revisado: mudanças focadas em hardening IAM condicional e documentação operacional; sem alteração de contrato de inputs dos workflows.

---

## Fechamento

### T3.1 Follow-up audit
- [ ] Reexecutar auditoria DevOps focada em CI/CD PRD.
- [ ] Reexecutar revisão arquitetural focada em drift e hardening.
- [ ] Gerar novo sumário executivo comparativo (antes/depois).
- [ ] Confirmar meta: zero findings `CRITICAL` e `HIGH` para CI/CD PRD.

### T3.2 Encerramento SDD
- [ ] Atualizar `TASKS.md` com todos os itens `[x]`.
- [ ] Atualizar status final dos artefatos conforme política do repo.
- [ ] Publicar links dos relatórios finais de remediação.
