# Spec: Audit Remediation — CI/CD, Infra e Arquitetura

> **Status:** Aprovado
> **Versão:** 0.1
> **Data:** 2026-05-11
> **Base de evidências:**
> - `.dadaia/reports/dd-chain-explorer/devops-engineer/2026-05-11T045924Z-audit.md`
> - `.dadaia/reports/dd-chain-explorer/software-architect/2026-05-11T045924Z-review.md`
> - `.dadaia/reports/dd-chain-explorer/review-summary/2026-05-11T045924Z-executive-summary.md`

---

## Contexto

A auditoria técnica identificou riscos críticos e altos no fluxo de deploy PRD, aderência Spec-Driven e hardening de infraestrutura. Esta spec define o escopo de remediação formal para eliminar os riscos e restaurar consistência entre contrato (`specs/`) e implementação (`.github/workflows`, `scripts/ci`, `services/**`).

## Objetivo

Remediar integralmente os achados críticos/altos da auditoria de 2026-05-11, com prioridade para segurança e produção, sem regressão de capacidade de deploy em DEV/HML/PRD.

## Escopo

### Em escopo
1. Corrigir inconsistência de secrets Databricks no deploy PRD.
2. Resolver drift entre spec DevOps e artefatos reais de CI/CD.
3. Reduzir shell inline em workflows críticos, extraindo para `scripts/ci/`.
4. Fortalecer guardrails de infraestrutura crítica (state bucket / IAM exception handling).
5. Publicar evidência de conformidade pós-remediação.

### Fora de escopo
1. Implementação da REST API de produto.
2. Refatoração ampla de arquitetura de dados (DLT/medallion).
3. Mudanças funcionais de negócio fora dos achados da auditoria.

## Itens de Remediação (priorizados)

### Fase 0 — Bloqueadores PRD

#### R0.1 — Corrigir token de PRD em deploy de DABs
- Problema: workflows de deploy Databricks para PRD usam token de HML.
- Resultado esperado: todo job PRD Databricks usa secret de PROD dedicado.
- Critério de aceite:
  - Não existe referência a `DATABRICKS_HML_TOKEN` em etapas de deploy/verify PRD.
  - Workflow falha explicitamente se `HOST` e `TOKEN` não forem do mesmo ambiente.

#### R0.2 — Gate de consistência de ambiente (policy de segurança)
- Problema: falta validação programática de pairing ambiente/secret.
- Resultado esperado: script de validação obrigatório antes de etapas PRD.
- Critério de aceite:
  - Script dedicado em `scripts/ci/`.
  - Reutilizado nos workflows de aplicações e all-applications.

### Fase 1 — Confiabilidade e Governança

#### R1.1 — Resolver drift spec/implementação em DevOps
- Problema: spec cita workflows/scripts ausentes (`plan_on_pr.yml`, `drift_detection.yml`, `tf_state_lock_check.sh`, `wait_eni_release.sh`, `deploy_env.sh`).
- Resultado esperado: contrato e implementação alinhados, sem itens fantasmas.
- Critério de aceite (uma das estratégias, explicitada no PLAN):
  - Estratégia A: implementar artefatos faltantes; ou
  - Estratégia B: atualizar spec para refletir estado real com justificativa e ADR operacional.

#### R1.2 — Extrair shell inline extenso para scripts versionados
- Problema: FR-DO-005 não atendido de forma consistente.
- Resultado esperado: blocos críticos em scripts reusáveis com `set -euo pipefail`.
- Critério de aceite:
  - Blocos >10 linhas nos workflows alvo migrados para `scripts/ci/`.
  - Scripts com validação de parâmetros e códigos de saída claros.

#### R1.3 — Revisar proteção do state bucket
- Problema: `prevent_destroy = false` em recurso crítico de state.
- Resultado esperado: proteção reforçada e política de exceção documentada.
- Critério de aceite:
  - Decisão explícita no código + documentação (se mantiver `false`, justificar controle compensatório).
  - Execução de destroy exige confirmação reforçada e trilha de auditoria.

### Fase 2 — Hardening estrutural

#### R2.1 — Reduzir permissões IAM amplas em PRD
- Problema: policy com `resources = ["*"]`.
- Resultado esperado: escopo mínimo viável por recurso/condição.
- Critério de aceite:
  - Redução de blast radius comprovada por diff de policy.
  - Exceções inevitáveis documentadas com racional técnico.

#### R2.2 — Formalizar exceções operacionais IaC-only
- Problema: workflows executam operações AWS CLI destrutivas fora de recursos Terraform.
- Resultado esperado: exceções registradas como decisão arquitetural operacional.
- Critério de aceite:
  - Documento de decisão referenciado nas specs de `devops`/`infrastructure`.
  - Checklist pós-execução para evitar drift não rastreado.

## Requisitos Funcionais

- **FR-AR-001:** Nenhum deploy PRD Databricks pode iniciar sem validação de consistência ambiente/secret.
- **FR-AR-002:** Spec DevOps deve refletir 100% dos workflows e scripts reais ativos.
- **FR-AR-003:** Workflows críticos devem delegar lógica shell complexa para `scripts/ci/`.
- **FR-AR-004:** Toda exceção de segurança/infra deve possuir justificativa técnica versionada.

## Requisitos Não Funcionais

- **NFR-AR-001:** Remediação não pode aumentar tempo total de pipeline PRD em mais de 15%.
- **NFR-AR-002:** Mudanças devem preservar approval gate `production` em todos os deploys PRD.
- **NFR-AR-003:** Não pode haver hardcode de secrets em código, workflow ou scripts.

## Dependências

1. Aprovação desta SPEC para abertura do PLAN.
2. Definição do owner principal por item (`devops-engineer`, `software-engineer`, `product-engineer`).
3. Disponibilidade dos secrets PRD corretos no GitHub Environment.

## Critérios de Conclusão

A remediação será considerada concluída quando:

1. Todos os itens Fase 0 e Fase 1 estiverem implementados e validados.
2. Itens Fase 2 estiverem implementados ou formalmente aceitos como débito com prazo.
3. Novo relatório de auditoria (follow-up) classificar zero findings `CRITICAL` e zero `HIGH` para CI/CD PRD.

## Riscos e Mitigações

- Risco: quebra de deploy por mudança de secret wiring.
  - Mitigação: validação em HML + smoke test de workflow antes de PRD.
- Risco: divergência contínua entre spec e implementação.
  - Mitigação: inserir checkpoint de drift no fluxo de release.
- Risco: regressão operacional ao extrair shell inline.
  - Mitigação: scripts com contratos de entrada/saída e logs estruturados.
