# Operational Exceptions — IaC-only Policy

> **Status:** Ativo
> **Data:** 2026-05-11
> **Escopo:** operações destrutivas fora do Terraform state estrito

## Contexto

A regra padrão é "Terraform como fonte única". Em teardown total, alguns recursos exigem operação AWS CLI explícita para evitar bloqueios operacionais:
- buckets com `prevent_destroy = true`
- buckets não vazios
- recursos já removidos do state por necessidade de recuperação/destruição ordenada

## Exceções Permitidas

1. `destroy_all_cloud_infra.yml` pode executar limpeza/deleção via AWS CLI para backend de state (`dm-chain-explorer-terraform-state`) e lock table.
2. `destroy_cloud_infra.yml` e `destroy_all_cloud_infra.yml` podem executar limpeza de S3/ECR antes do `terraform destroy`.

## Guardrails Obrigatórios

1. Confirmação manual explícita (`DESTROY` ou `DESTROY ALL`).
2. Execução apenas via GitHub Actions com `environment: production` para PRD.
3. Registro no `GITHUB_STEP_SUMMARY` dos recursos afetados e status final.
4. Nunca usar esses comandos fora dos workflows versionados.

## Checklist Pós-operação

1. Validar que não há recursos órfãos críticos (`S3`, `DynamoDB lock`, `ECR`) fora do esperado.
2. Reexecutar `terraform plan` nos módulos remanescentes para confirmar ausência de drift inesperado.
3. Registrar resultado no relatório da remediação (`specs/domains/devops/audit-remediation-2026-05/TASKS.md`).
4. Se houver divergência, abrir item de remediação dedicado antes do próximo deploy PRD.
