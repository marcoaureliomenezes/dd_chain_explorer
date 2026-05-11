# Plan: Audit Remediation — CI/CD, Infra e Arquitetura

> **Spec:** `specs/domains/devops/audit-remediation-2026-05/SPEC.md`
> **Status:** Aprovado
> **Data:** 2026-05-11

---

## Estratégia de Execução

Implementar em 3 ondas:

1. **Fase 0 (bloqueadores PRD):** corrigir credenciais e adicionar validação obrigatória de ambiente.
2. **Fase 1 (governança e confiabilidade):** eliminar drift spec/implementação e extrair shell inline crítico.
3. **Fase 2 (hardening):** reduzir permissões IAM amplas e formalizar exceções operacionais IaC.

A execução deve preservar deploy em `DEV`/`HML` e gate `production` para `PRD`.

---

## Plano Detalhado

### Etapa P0 — Preparação e baseline

- Confirmar baseline dos workflows alvo:
  - `.github/workflows/deploy_dm_applications.yml`
  - `.github/workflows/deploy_all_dm_applications.yml`
  - `.github/workflows/deploy_cloud_infra.yml`
- Congelar evidências atuais em report de referência (já existente em `.dadaia/reports/...`).
- Definir matriz de secrets por ambiente (HML vs PRD) como contrato operacional.

**Saída:** checklist de baseline + matriz ambiente/secret versionada em docs/spec.

### Etapa P1 — Fase 0 (PRD blockers)

#### P1.1 Corrigir wiring de secrets Databricks em PRD

- Substituir `DATABRICKS_HML_TOKEN` por secret de PRD em todos os steps PRD de DABs.
- Validar que blocos HML continuam com token HML e blocos PRD com token PRD.

#### P1.2 Introduzir gate de consistência ambiente/secret

- Criar script `scripts/ci/validate_env_secret_pair.sh`.
- Regras mínimas:
  - Falhar se `DATABRICKS_HOST` e token não corresponderem ao mesmo ambiente.
  - Emitir erro explícito e abortar job antes de deploy/tag.
- Integrar script no início dos jobs PRD de:
  - `deploy_dm_applications.yml`
  - `deploy_all_dm_applications.yml`

**Saída:** deploy PRD bloqueado por validação de pairing inválido.

### Etapa P2 — Fase 1 (governança e confiabilidade)

#### P2.1 Resolver drift spec x implementação

Escolher e aplicar uma estratégia única:
- **A)** implementar artefatos faltantes (`plan_on_pr.yml`, `drift_detection.yml`, scripts ausentes), ou
- **B)** atualizar `specs/domains/devops/SPEC.md` para refletir estado real.

Para este ciclo, default: **Estratégia B** (rápida, consistente com estado atual), registrando backlog para Estratégia A futura.

#### P2.2 Extrair shell inline crítico para `scripts/ci/`

- Identificar blocos >10 linhas em workflows críticos.
- Extrair para scripts dedicados com:
  - `set -euo pipefail`
  - validação de parâmetros obrigatórios
  - códigos de saída estáveis
- Prioridade inicial:
  - deploy/verify de DABs
  - rotinas de teardown com repetição de lógica S3/ECR

#### P2.3 Revisar proteção do state bucket

- Avaliar mudança de `prevent_destroy` e impactos em destroy controlado.
- Se mantido `false`, documentar controle compensatório obrigatório (confirmação + segregação de permissão).

**Saída:** spec e código alinhados, lógica CI mais modular, state com decisão explícita.

### Etapa P3 — Fase 2 (hardening estrutural)

#### P3.1 Reduzir permissões IAM amplas

- Revisar statements com `resources = ["*"]`.
- Restringir por ARN/condição onde tecnicamente possível sem quebrar integração Databricks.
- Documentar exceções remanescentes com justificativa e risco residual.

#### P3.2 Formalizar exceções operacionais IaC

- Criar ADR/nota operacional para operações CLI destrutivas fora de recursos Terraform.
- Definir checklist pós-operação para mitigar drift.

**Saída:** postura de segurança e governança endurecida.

---

## Testes e Validação

### Validação técnica mínima

1. Lint de workflows YAML alterados.
2. Execução local dos scripts novos com casos:
   - sucesso (pairing correto)
   - falha controlada (pairing incorreto)
3. Verificação estática de ausência de `DATABRICKS_HML_TOKEN` em blocos PRD.
4. `terraform validate` nos módulos tocados.

### Validação funcional de pipeline

1. Run em HML (smoke) sem regressão de deploy.
2. Simulação de gate PRD (job deve bloquear em pairing inválido).
3. Confirmação de manutenção do `environment: production` nos jobs PRD.

### Critério de aceite global

- Zero finding `CRITICAL` e `HIGH` em follow-up para CI/CD PRD.

---

## Ordem de Entrega

1. Pull request 1: Fase 0.
2. Pull request 2: Fase 1.
3. Pull request 3: Fase 2.
4. Re-audit final com relatório consolidado pós-remediação.

---

## Riscos de Implementação

- Mudança de secret names pode quebrar jobs existentes.
- Extração de shell inline pode alterar comportamento implícito.
- Restrição de IAM pode impactar integrações Databricks.

Mitigação: rollout por fases, smoke tests por ambiente, e rollback por PR isolado.
