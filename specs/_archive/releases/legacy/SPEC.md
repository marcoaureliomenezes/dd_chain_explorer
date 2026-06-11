# Spec: DD Chain Explorer — Produto

> **Status:** Implementado (com exceção do domínio `rest-api` em `applications/`)
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/product.md`, `specs/memory/architecture.md`, `specs/memory/constitution.md`

---

## Contexto

DD Chain Explorer é uma plataforma de dados Ethereum em tempo real. Captura transações e blocos da mainnet Ethereum, processa via arquitetura Medallion no Databricks e serve analytics via dashboards e API REST.

---

## Domínios

| Domínio | Escopo | Status |
|---------|--------|--------|
| `applications` | Streaming (Docker/ECS), Lambda, dm-chain-utils, REST API | Implementado (REST API pendente) |
| `infrastructure` | Terraform, AWS, ambientes DEV/HML/PRD | Implementado |
| `data-engineering` | DLT pipelines, batch jobs, modelo Medallion | Implementado |
| `data-analytics` | Dashboards Lakeview, Genie Spaces, Alerts | Implementado (dashboards quebrados) |
| `devops` | GitHub Actions, GitFlow, versionamento | Implementado |

---

## User Stories de Produto

### US-P001 — Captura contínua de blocos Ethereum
Como plataforma de dados, quero detectar e capturar cada bloco minerado na mainnet Ethereum em até 2 segundos, para que pipelines downstream recebam dados com latência mínima.

### US-P002 — Decodificação de calldata
Como plataforma de dados, quero decodificar o campo `input` de cada transação em nome de método e parâmetros legíveis, para que analytics Gold possa classificar tipos de transação.

### US-P003 — Camada Gold para analytics
Como consumidor de dados, quero tabelas Gold agregadas (contratos populares, gas, transferências P2P, métricas de rede) disponíveis via SQL Warehouse e REST API.

### US-P004 — Visibilidade operacional
Como operador, quero dashboards e alertas que monitorem saúde da pipeline e consumo de API keys, para que problemas sejam detectados antes de impactar dados.

### US-P005 — API REST pública (pendente)
Como consumidor externo, quero acessar dados Gold via endpoints HTTP, sem precisar de acesso ao Databricks SQL Warehouse.

---

## Requisitos Não-Funcionais

- **NFR-P001:** Latência Ethereum → S3 Bronze < 2 minutos.
- **NFR-P002:** Latência S3 → Gold (DLT trigger + pipeline) < 5 minutos.
- **NFR-P003:** REST API: latência p95 < 2 segundos sob carga normal.
- **NFR-P004:** Nenhum segredo hardcoded em nenhum arquivo — ver `constitution.md`.
- **NFR-P005:** Todo recurso AWS gerenciado exclusivamente via Terraform.
