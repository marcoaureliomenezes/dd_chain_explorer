---
applyTo: "dd_chain_explorer/**"
sync_version: "1.0.0"
---

# Documentação — DD Chain Explorer

## Estrutura Oficial de Documentação

Todo projeto com pasta `.git/` deve seguir exatamente a estrutura abaixo. Agentes **não devem** criar arquivos `.md` fora desta lista sem aprovação explícita do usuário.

### Arquivos Permitidos (lista exaustiva)

#### Arquitetura (`docs/architecture/`) — editáveis manualmente

| Arquivo | Escopo |
|---------|--------|
| `docs/architecture/01_architecture.md` | Arquitetura geral, topologia de rede, segurança |
| `docs/architecture/02_data_capture.md` | Jobs de streaming Python, Kinesis, DynamoDB, Lambda |
| `docs/architecture/03_data_processing.md` | DLT pipelines, modelo Medallion, Databricks Workflows |
| `docs/architecture/04_data_ops.md` | Makefile, CI/CD, Terraform, DABs, GitFlow |
| `docs/architecture/05_data_serving.md` | Objetos Gold, dashboards, APIs, segurança de dados |

Somente estes 5 arquivos são permitidos dentro de `docs/architecture/`. Nenhum outro `.md` deve ser criado nessa pasta.

#### Raiz de `docs/` — editáveis manualmente

| Arquivo | Escopo |
|---------|--------|
| `docs/06_integration_tests_specs.md` | Especificações e gates dos testes de integração HML/DEV |
| `docs/ROADMAP.md` | Consolidação de todos os TODOs — única fonte de verdade |

#### Relatórios (`docs/reports/`) — **GERADOS por prompt-files, não editar manualmente**

| Arquivo | Gerado por |
|---------|----------|
| `docs/reports/report_finops.md` | `.github/prompts/report-finops.prompt.md` |
| `docs/reports/report_security.md` | `.github/prompts/report-security.prompt.md` |

> **Importante**: estes arquivos são gerados automaticamente por prompt-files. O workflow `update-docs` **não deve** incluí-los no escopo de atualização de documentação e não deve editá-los.

#### Análises (`docs/analysis/`) — **efêmeros, não rastreados**

Arquivos em `docs/analysis/` são criados por agentes de AI para análises pontuais (comparar opções de arquitetura, redução de custos, optimização de performance). São lidos pelo usuário e apagados. O workflow `update-docs` **não deve** rastrear, editar ou referenciar arquivos nessa pasta.

#### READMEs de componentes (`apps/`)

| Arquivo | Escopo |
|---------|--------|
| `apps/dabs/README.md` | DABs: pipelines DLT, workflows, deploy |
| `apps/docker/README.md` | Streaming apps: 5 jobs, Kinesis, ECS Fargate |
| `apps/lambda/README.md` | Lambda functions: contracts_ingestion, gold_to_dynamodb |

#### Raiz do repositório

- `README.md` — visão geral do projeto

---

## Guardrail — Nunca Crie Markdown Fora da Lista

**Não crie arquivos `.md` fora da lista acima.** Se detectar um `.md` em local não permitido, **pergunte ao usuário** antes de qualquer ação:

> "Encontrei `{arquivo}` fora da estrutura oficial de documentação. Deseja deletá-lo?"

Peça confirmação individual para cada arquivo stray encontrado. Nunca delete sem confirmação explícita.

---

## Quando Atualizar a Documentação

| Mudança em | Documento(s) a atualizar |
|------------|---------------------------|
| `apps/docker/onchain-stream-txs/` | `docs/architecture/02_data_capture.md`, `apps/docker/README.md` |
| `apps/lambda/` | `docs/architecture/02_data_capture.md`, `apps/lambda/README.md` |
| `apps/dabs/src/streaming/` | `docs/architecture/03_data_processing.md`, `apps/dabs/README.md` |
| `apps/dabs/src/batch/` | `docs/architecture/03_data_processing.md`, `apps/dabs/README.md` |
| `apps/dabs/resources/` | `docs/architecture/03_data_processing.md`, `docs/architecture/04_data_ops.md`, `apps/dabs/README.md` |
| `apps/dabs/databricks.yml` | `docs/architecture/03_data_processing.md`, `docs/architecture/04_data_ops.md`, `apps/dabs/README.md` |
| `services/dev/` | `docs/architecture/01_architecture.md`, `docs/architecture/04_data_ops.md` |
| `services/prd/` | `docs/architecture/01_architecture.md`, `docs/architecture/04_data_ops.md` |
| `.github/workflows/` | `docs/architecture/04_data_ops.md` |
| `Makefile` | `docs/architecture/04_data_ops.md` |
| `utils/` | `docs/architecture/02_data_capture.md` |
| `scripts/` | `docs/architecture/04_data_ops.md` |
| `VERSION` | `docs/architecture/04_data_ops.md`, `README.md` |

---

## Regras de Conteúdo

- **Idioma**: `docs/architecture/` e `docs/` sempre em **português brasileiro (pt-BR)**. READMEs de `apps/` mantêm o idioma existente.
- **Diagramas**: usar **Mermaid** inline — sem imagens externas.
- **Caminhos**: sempre relativos à raiz de `dd_chain_explorer/` (ex: `apps/dabs/`, não `dabs/`).
- **TODOs**: somente no `docs/ROADMAP.md`. Nunca adicionar `TODO-X##` nos docs `01–05` ou `06_integration_tests_specs.md`.
- **Seção "Referências de Arquivos"**: obrigatória no final de cada doc `architecture/01–05`.
