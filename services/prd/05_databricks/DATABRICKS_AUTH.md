################################################################################
# terraform_prd/7_databricks/DATABRICKS_AUTH.md
#
# Como configurar autenticação Databricks para este módulo Terraform.
#
# NUNCA USE secrets.tfvars com credenciais hardcoded.
# As credenciais ficam em ~/.databrickscfg (nunca versionado) ou em
# variáveis de ambiente (CI/CD).
################################################################################

## Autenticação local (desenvolvimento)

Configure o arquivo `~/.databrickscfg` com um perfil `[prd]`:

```ini
[prd]
host          = https://accounts.cloud.databricks.com
account_id    = <uuid-da-sua-conta>
client_id     = <client-id-do-service-principal>
client_secret = <client-secret-do-service-principal>
```

O Service Principal e as credenciais OAuth (client_id + client_secret) são
criados em:
  https://accounts.cloud.databricks.com → Settings → Service Principals

Para verificar:
```bash
databricks auth describe --profile prd
```

## Autenticação em CI/CD (GitHub Actions)

Configure os seguintes GitHub Secrets no repositório
(Settings → Secrets and variables → Actions):

| Secret                        | Valor                                      |
|-------------------------------|-------------------------------------------|
| `DATABRICKS_ACCOUNT_ID`       | UUID da conta Databricks                  |
| `DATABRICKS_CLIENT_ID`        | Client ID do Service Principal            |
| `DATABRICKS_CLIENT_SECRET`    | Client Secret do Service Principal        |

As env vars têm **precedência automática** sobre o `profile` no provider.
Não é necessária nenhuma alteração no código Terraform para CI/CD funcionar.

## Uso

```bash
# Local (usa perfil ~/.databrickscfg [prd])
terraform apply

# Sobrescrever o perfil pontualmente
terraform apply -var="databricks_accounts_profile=prd-staging"
```
