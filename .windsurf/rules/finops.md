---
trigger: manual
---

# FinOps Rules

## Separação de Responsabilidades entre Documentos

- **`docs/04_data_ops.md`**: contém **exclusivamente** informações de arquitetura cloud (AWS e Databricks) — recursos, componentes, fluxos de dados, CI/CD, estrutura Terraform. **Nenhuma informação de custo deve constar neste arquivo.**
- **`docs/06_fin_ops.md`**: é a **fonte da verdade** sobre todos os custos do projeto. Toda estimativa de preço, custo real medido, análise de ROI e avaliação de novos recursos deve ser documentada aqui.

## Estrutura Obrigatória de `06_fin_ops.md`

O arquivo deve manter as seguintes seções (nesta ordem):

1. **Inventário de Recursos por Ambiente** — tabelas DEV / HML / PRD com recurso, spec, custo estimado e custo real.
2. **Custos Databricks** — DBUs por cluster/pipeline/schedule.
3. **Análise de Custo Real** — dados obtidos via AWS Cost Explorer ou SDK, por ambiente, por serviço, por tag.
4. **Budget Alerts** — limites configurados + alertas ativos.
5. **Estratégias de Otimização** — idle resources, rightsizing, Spot, Reserved, Savings Plans.
6. **Avaliação de Novos Recursos** — uma sub-seção por recurso avaliado (ex: `### NAT Gateway`, `### EKS`). Cada avaliação inclui: motivação, pricing estimado (via AWS Calculator), alternativas, decisão.

## Fontes de Dados de Custo

### Estimativas (Pricing)
- Usar **AWS Pricing Calculator** (`https://calculator.aws/`) para gerar estimativas detalhadas por recurso, considerando **região `sa-east-1`** e specs reais dos recursos.
- Para pesquisa de preços via web, consultar as páginas oficiais de pricing da AWS:
  - `https://aws.amazon.com/kinesis/data-streams/pricing/`
  - `https://aws.amazon.com/fargate/pricing/`
  - `https://aws.amazon.com/s3/pricing/`
  - `https://aws.amazon.com/dynamodb/pricing/`
  - `https://aws.amazon.com/firehose/pricing/`
  - `https://aws.amazon.com/cloudwatch/pricing/`
  - `https://aws.amazon.com/lambda/pricing/`
  - `https://aws.amazon.com/sqs/pricing/`

### Custos Reais (Medidos)
- Usar **AWS Cost Explorer** via boto3 SDK:
  ```python
  import boto3
  ce = boto3.client("ce", region_name="us-east-1")  # Cost Explorer é global (us-east-1)
  response = ce.get_cost_and_usage(
      TimePeriod={"Start": "YYYY-MM-01", "End": "YYYY-MM-DD"},
      Granularity="MONTHLY",
      Filter={"Tags": {"Key": "environment", "Values": ["dev", "hml", "prd"]}},
      GroupBy=[
          {"Type": "TAG", "Key": "environment"},
          {"Type": "DIMENSION", "Key": "SERVICE"},
      ],
      Metrics=["UnblendedCost"],
  )
  ```
- Alternativa via AWS CLI:
  ```bash
  aws ce get-cost-and-usage \
    --time-period Start=2025-01-01,End=2025-02-01 \
    --granularity MONTHLY \
    --metrics UnblendedCost \
    --group-by Type=TAG,Key=environment Type=DIMENSION,Key=SERVICE \
    --region us-east-1
  ```
- **Tags obrigatórias** para rastreamento de custos (já presentes em `common_tags`):
  - `environment`: `dev` | `hml` | `prd`
  - `project`: `dd-chain-explorer`
  - `cost-center`: `data-engineering`
  - `managed-by`: `terraform`

## Regras de Atualização

- **Estimativas** devem ser atualizadas sempre que um novo recurso for adicionado ou uma spec for alterada no Terraform.
- **Custos reais** devem ser atualizados mensalmente via workflow `update_finops`.
- Toda sessão que adicionar/modificar recursos AWS deve verificar se `06_fin_ops.md` está desatualizado e propor atualização.
- Ao avaliar um novo recurso (ex: NAT Gateway, EKS, MSK), **criar uma sub-seção em "Avaliação de Novos Recursos"** antes de decidir pela implementação.

## Databricks DBU Pricing (sa-east-1)

| Tier | Tipo | DBU/hora | Preço USD/DBU |
|------|------|----------|---------------|
| Serverless DLT | Streaming | variável | ~$0.07–0.14/DBU |
| Interactive | Jobs compute | variável | ~$0.22/DBU |
| Jobs | Automated | variável | ~$0.15/DBU |

> Consultar `https://www.databricks.com/product/pricing` para valores atualizados.
