# 06 — Roadmap

## Visão Geral

Este documento consolida as melhorias pendentes do projeto, organizadas por prioridade e fase de execução. Cada item referencia o TODO original para rastreabilidade.

> Os itens concluídos foram removidos do roadmap. Consulte o histórico de commits e os documentos 01–05 para o registro completo de implementações.
> TODOs consolidados (A02→A11, C07→A11) permanecem marcados com `[x]` nos documentos de origem.

**TODOs em aberto: 15** (6 Arquitetura + 2 Captura + 2 Processamento + 4 DataOps + 2 Serving — excluindo 2 consolidados)

---

## Fase 0 — Blockers (P0)

Itens que impedem a operação em produção. Devem ser resolvidos antes de qualquer outro trabalho.

| Prioridade | TODO | Área | Descrição | Esforço |
|------------|------|------|-----------|---------|
| 🔴 P0 | TODO-O11 | DataOps | Hardening CI/CD: testar e validar os 4 tipos de deploy (Docker→ECS, lib Python, Terraform plan/apply, DABs deploy) | Alto |
| 🔴 P0 | TODO-O12 | DataOps | Validar PROD end-to-end: streaming ECS → MSK → DLT Databricks → Gold tables | Alto |
| 🔴 P0 | TODO-P01 | Processamento | Validar DLT contínuo com MSK + IAM auth em PROD (pré-requisito para TODO-O12) | Alto |

---

## Fase 1 — Resiliência, Observabilidade e Ingestão

Melhorias que aumentam a confiabilidade, visibilidade e paridade DEV/PROD.

| Prioridade | TODO | Área | Descrição | Esforço |
|------------|------|------|-----------|---------|
| 🟡 P1 | TODO-A11 | Arquitetura | Substituir Spark Kafka→S3 por **Kafka Connect S3 Sink** (DEV+PROD). Consolida A02+C07 | Alto |
| 🟡 P1 | TODO-A06 | Arquitetura | Implementar observabilidade PROD (CloudWatch/Prometheus+Grafana) | Alto |
| 🟡 P1 | TODO-O08 | DataOps | CloudWatch Dashboards ou Grafana para ECS + MSK + DynamoDB | Alto |
| 🟡 P1 | TODO-C08 | Captura | Métricas Prometheus nos jobs de streaming (throughput, latência, erros) | Médio |
| 🟡 P1 | TODO-O10 | DataOps | Notificações Slack/Teams para falhas CI/CD e alertas de infra | Médio |

---

## Fase 2 — Otimizações e Eficiência

Performance, custo e maturidade operacional.

| Prioridade | TODO | Área | Descrição | Esforço |
|------------|------|------|-----------|---------|
| 🟠 P2 | TODO-A12 | Arquitetura | Estudo de custo ECS Fargate vs EC2: duplicar services, rodar 24h, comparar consumo | Médio |
| 🟠 P2 | TODO-C10 | Captura | Batched RPC calls nos Jobs 3 e 4 (JSON-RPC batch) | Médio |
| 🟠 P2 | TODO-A04 | Arquitetura | TLS para Kafka em PROD (avaliar SASL/TLS vs security groups) | Médio |
| 🟠 P2 | TODO-A07 | Arquitetura | Avaliar NAT Gateway na VPC (segurança vs custo) | Baixo |

---

## Fase 3 — Evolução da Plataforma

Funcionalidades novas e expansão do escopo.

| Prioridade | TODO | Área | Descrição | Esforço |
|------------|------|------|-----------|---------|
| 🔵 P3 | TODO-A03 | Arquitetura | Airflow PROD (MWAA vs ECS Fargate vs Docker Swarm) | Alto |
| 🔵 P3 | TODO-P09 | Processamento | Avaliar migração para MWAA em PROD | Alto |
| 🔵 P3 | TODO-A10 | Arquitetura | Criar ambiente de staging/homologação | Alto |
| 🔵 P3 | TODO-S06 | Serving | REST API (FastAPI no ECS ou Databricks SQL Statement API) | Alto |
| 🔵 P3 | TODO-S10 | Serving | Página web pública com métricas Ethereum (depende de TODO-S06) | Alto |

---

## Resumo por Área

| Área | Total | Fase 0 | Fase 1 | Fase 2 | Fase 3 |
|------|-------|--------|--------|--------|--------|
| Arquitetura (A) | 6 | — | 2 | 2 | 2 |
| Captura (C) | 2 | — | 1 | 1 | — |
| Processamento (P) | 2 | 1 | — | — | 1 |
| DataOps (O) | 4 | 2 | 2 | — | — |
| Serving (S) | 2 | — | — | — | 2 |
| **Total** | **15** | **3** | **5** | **4** | **5** |

> **Nota**: TODO-A02 e TODO-C07 foram consolidados no TODO-A11 (não contabilizados no total).

---

## Critérios de Priorização

| Prioridade | Critério |
|------------|----------|
| 🔴 P0 | **Blocker** — Impede operação em produção. CI/CD não validado, ambiente PROD não funcional |
| 🟡 P1 | **Alta** — Resiliência, observabilidade, paridade DEV/PROD, segurança |
| 🟠 P2 | **Média** — Otimização de performance, custo, maturidade operacional |
| 🔵 P3 | **Baixa** — Evolução futura, funcionalidades novas de alto esforço |

---

## Dependências entre TODOs

```mermaid
flowchart TD
    O11["🔴 TODO-O11<br/>Hardening CI/CD"] --> O12["🔴 TODO-O12<br/>Validar PROD E2E"]
    P01["🔴 TODO-P01<br/>DLT contínuo PROD"] --> O12
    A11["🟡 TODO-A11<br/>Kafka Connect S3 Sink"] --> O12
    A06["🟡 TODO-A06<br/>Observabilidade PROD"] --> O08["🟡 TODO-O08<br/>CloudWatch/Grafana"]
    A06 --> C08["🟡 TODO-C08<br/>Prometheus streaming"]
    A04["🟠 TODO-A04<br/>TLS Kafka"] -.-> P01
    A12["🟠 TODO-A12<br/>Fargate vs EC2"] -.-> O12
    S06["🔵 TODO-S06<br/>REST API"] --> S10["🔵 TODO-S10<br/>Web pública"]
    A03["🔵 TODO-A03<br/>Airflow PROD"] --> P09["🔵 TODO-P09<br/>MWAA"]
```

---

## Referências de Arquivos

| Documento | Arquivo | TODOs |
|-----------|---------|-------|
| 01 — Arquitetura | `docs/01_architecture.md` | ~~TODO-A02~~, A03, A04, A06, A07, A10, **A11**, **A12** |
| 02 — Captura de Dados | `docs/02_data_capture.md` | ~~TODO-C07~~, C08, C10 |
| 03 — Processamento de Dados | `docs/03_data_processing.md` | TODO-P01, P09 |
| 04 — DataOps | `docs/04_data_ops.md` | TODO-O08, O10, **O11**, **O12** |
| 05 — Data Serving | `docs/05_data_serving.md` | TODO-S06, S10 |

