---
description: Update 06_fin_ops.md with real AWS costs and refreshed price estimates
---

# Update FinOps Report

Updates `docs/06_fin_ops.md` with real AWS costs (via Cost Explorer SDK) and refreshed pricing estimates (via AWS Calculator research). Run monthly or after any infrastructure change.

## Step 1 — Collect real costs via AWS Cost Explorer

Run the following Python script to fetch costs by environment and service for the current and previous month:

```bash
python3 - <<'EOF'
import boto3, json
from datetime import date, timedelta

ce = boto3.client("ce", region_name="us-east-1")

# Current month
today = date.today()
start = today.replace(day=1).isoformat()
end = today.isoformat()

resp = ce.get_cost_and_usage(
    TimePeriod={"Start": start, "End": end},
    Granularity="MONTHLY",
    Filter={
        "Tags": {
            "Key": "project",
            "Values": ["dd-chain-explorer"]
        }
    },
    GroupBy=[
        {"Type": "TAG",       "Key": "environment"},
        {"Type": "DIMENSION", "Key": "SERVICE"},
    ],
    Metrics=["UnblendedCost"],
)

for group in resp["ResultsByTime"][0]["Groups"]:
    env, svc = group["Keys"]
    cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
    if cost > 0.001:
        print(f"{env:<20} {svc:<45} ${cost:.4f}")
EOF
```

Alternatively via AWS CLI:
```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --filter '{"Tags":{"Key":"project","Values":["dd-chain-explorer"]}}' \
  --group-by Type=TAG,Key=environment Type=DIMENSION,Key=SERVICE \
  --metrics UnblendedCost \
  --region us-east-1 \
  --query 'ResultsByTime[0].Groups[?Metrics.UnblendedCost.Amount > `0.001`].[Keys[0],Keys[1],Metrics.UnblendedCost.Amount]' \
  --output table
```

## Step 2 — Collect Databricks DBU consumption

```bash
# Via Databricks REST API (requires DATABRICKS_HOST + DATABRICKS_TOKEN)
curl -s -X GET "$DATABRICKS_HOST/api/2.0/clusters/list" \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" | jq '.clusters[] | {name:.cluster_name, dbu_hour:.dbu_per_hour}'
```

For DLT pipeline DBU usage, check the Databricks UI: **Workflows → Pipeline → Run details → DBU consumption**.

## Step 3 — Research updated pricing estimates (when specs changed)

Use `read_url_content` tool to fetch current pricing from AWS official pages for any resource that changed:

| Resource | Pricing URL |
|----------|-------------|
| ECS Fargate | `https://aws.amazon.com/fargate/pricing/` |
| Kinesis Data Streams | `https://aws.amazon.com/kinesis/data-streams/pricing/` |
| Kinesis Firehose | `https://aws.amazon.com/firehose/pricing/` |
| S3 | `https://aws.amazon.com/s3/pricing/` |
| DynamoDB | `https://aws.amazon.com/dynamodb/pricing/` |
| CloudWatch | `https://aws.amazon.com/cloudwatch/pricing/` |
| Lambda | `https://aws.amazon.com/lambda/pricing/` |
| SQS | `https://aws.amazon.com/sqs/pricing/` |

For detailed multi-resource estimates, use AWS Pricing Calculator: `https://calculator.aws/`
Always use **region: `sa-east-1` (São Paulo)** — prices are ~50% higher than us-east-1.

## Step 4 — Update `docs/06_fin_ops.md`

Update the following sections with data collected in Steps 1–3:

1. **Section 1 — Inventário de Recursos por Ambiente**: update "Custo Real" column for DEV, HML, PRD tables.
2. **Section 3 — Análise de Custo Real**: add a dated entry (e.g. `#### Medição: YYYY-MM`) with the output from Step 1.
3. **Section 4 — Budget Alerts**: verify alerts are still configured for current spend levels.
4. **Section 5 — Estratégias de Otimização**: update any items resolved or newly identified.

## Step 5 — Commit the updated FinOps report

```bash
git add docs/06_fin_ops.md
git commit -m "docs(finops): update cost report $(date +%Y-%m)"
git push origin develop
```

## Notes

- Cost Explorer data has **24–48h lag** — run on the 3rd of each month for complete previous month.
- Tag coverage may be incomplete for resources created before tagging policy was enforced — check AWS Cost Explorer "Tag coverage" report.
- For new resource evaluation (e.g., NAT Gateway, EKS), add a sub-section under **"Avaliação de Novos Recursos"** in `06_fin_ops.md` *before* implementing.
