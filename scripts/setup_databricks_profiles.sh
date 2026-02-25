#!/usr/bin/env bash
###############################################################################
# scripts/setup_databricks_profiles.sh
#
# Configura os perfis da CLI Databricks (~/.databrickscfg) para este projeto.
#
# Perfis criados:
#   [prd]     → Databricks account-level (MWS) — criação de workspace, metastore
#   [dev]     → Databricks Free Edition         — desenvolvimento local
#
# Pré-requisito: Databricks CLI instalado
#   pip install databricks-cli  OU  brew install databricks
#
# Uso:
#   chmod +x scripts/setup_databricks_profiles.sh
#   ./scripts/setup_databricks_profiles.sh
###############################################################################

set -e

echo ""
echo "=== Configuração de perfis Databricks (~/.databrickscfg) ==="
echo ""

###############################################################################
# Perfil PRD — Account-level (OAuth M2M com Service Principal)
# Usado por: infra-prd/terraform/7_databricks
###############################################################################
echo "--- [prd] — Databricks Account Level (para infra-prd/terraform) ---"
echo "Host: https://accounts.cloud.databricks.com"
echo ""
echo "Credenciais OAuth M2M obtidas em:"
echo "  https://accounts.cloud.databricks.com → Settings → Service Principals → <SP> → OAuth secrets"
echo ""
echo "Configurando perfil [prd]..."
databricks configure --profile prd
echo "Perfil [prd] configurado."
echo ""

###############################################################################
# Perfil DEV — Workspace Free Edition (Personal Access Token)
# Usado por: infra-dev/terraform
###############################################################################
echo "--- [dev] — Databricks Free Edition (para infra-dev/terraform) ---"
echo "Host: https://community.cloud.databricks.com"
echo ""
echo "Token obtido em:"
echo "  https://community.cloud.databricks.com → Settings → Developer → Access tokens"
echo ""
echo "Configurando perfil [dev]..."
databricks configure --profile dev
echo "Perfil [dev] configurado."
echo ""

###############################################################################
# Verificação
###############################################################################
echo "=== Verificando perfis ==="
echo ""
echo "Perfil [prd]:"
databricks auth describe --profile prd 2>/dev/null || echo "  erro ao verificar [prd]"
echo ""
echo "Perfil [dev]:"
databricks auth describe --profile dev 2>/dev/null || echo "  erro ao verificar [dev]"
echo ""
echo "Perfis configurados em: ~/.databrickscfg"
echo ""
echo "Para usar no terraform:"
echo "  cd infra-prd/terraform/7_databricks && terraform apply"
echo "  cd infra-dev/terraform && terraform apply"
echo ""
echo "IMPORTANTE: ~/.databrickscfg NUNCA deve ser commitado. Verifique seu ~/.gitignore global."



# stop and delete all containers

