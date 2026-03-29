
> **DEV atualizado em:** 2026-03-29 | **DEV fingerprint:** `N/A...` | **Gerado por:** `/update-lake-schemas`



## DEV (Catalog: `dev`)

### Visão Geral

| Métrica | Valor |
|---------|-------|
| Total de Schemas | 0 |
| Total de Tabelas | 0 |
| Tamanho Total Estimado | 0.0 GB |
| Total de Arquivos | 0 |
| Total de Linhas | 0 |
| Última Atualização | 2026-03-29 |

### Schemas e Tabelas

### Como Usar esses Dados (Serving Layer)

Tabelas Silver (prefixo `s_`) e Gold (prefixo `g_` ou schemas `gold*`) estão otimizadas para:
- **Dashboards Lakeview**: tabelas com prefixo `s_` e `g_` são candidatas
- **Genie Spaces**: use tabelas Gold com agregações e dimensões claras
- **Power BI / BI Tools**: exporte via Gold layer via S3 (veja `04_export_gold_to_s3.py`)

