#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# backup_databricks_metadata.sh
#
# Exporta DDL (SHOW CREATE TABLE) de todas as tabelas no Unity Catalog
# para um arquivo SQL versionável no repositório.
#
# Uso:
#   ./scripts/backup_databricks_metadata.sh [CATALOG] [PROFILE]
#
# Exemplos:
#   ./scripts/backup_databricks_metadata.sh prd prd-workspace
#   ./scripts/backup_databricks_metadata.sh dev              # profile default
#
# Pré-requisitos:
#   - Databricks CLI v0.200+ instalado e configurado
#   - Perfil no ~/.databrickscfg com acesso ao workspace
#
# Saída:
#   docs/databricks_metadata_backup.sql
# ---------------------------------------------------------------------------
set -euo pipefail

CATALOG="${1:-prd}"
PROFILE="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${SCRIPT_DIR}/../docs/databricks_metadata_backup.sql"

PROFILE_FLAG=""
if [[ -n "$PROFILE" ]]; then
  PROFILE_FLAG="--profile $PROFILE"
fi

echo "-- ============================================================="
echo "-- Databricks Unity Catalog Metadata Backup"
echo "-- Catalog: ${CATALOG}"
echo "-- Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "-- ============================================================="
echo ""

# Listar todos os schemas do catálogo
SCHEMAS=$(databricks sql execute $PROFILE_FLAG \
  --statement "SHOW SCHEMAS IN \`${CATALOG}\`" \
  --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for row in data.get('result', {}).get('data_array', []):
    schema = row[0] if isinstance(row, list) else row
    if schema not in ('information_schema', 'default'):
        print(schema)
" 2>/dev/null || echo "")

if [[ -z "$SCHEMAS" ]]; then
  echo "WARN: Nenhum schema encontrado ou falha na conexão. Tentando schemas conhecidos..."
  SCHEMAS="b_ethereum s_apps s_logs g_api_keys g_network"
fi

{
  echo "-- ============================================================="
  echo "-- Databricks Unity Catalog Metadata Backup"
  echo "-- Catalog: ${CATALOG}"
  echo "-- Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "-- ============================================================="
  echo ""
  echo "-- Recreate catalog and schemas"
  echo "CREATE CATALOG IF NOT EXISTS \`${CATALOG}\`;"
  echo ""

  for SCHEMA in $SCHEMAS; do
    echo "CREATE SCHEMA IF NOT EXISTS \`${CATALOG}\`.\`${SCHEMA}\`;"
  done
  echo ""

  for SCHEMA in $SCHEMAS; do
    echo "-- -----------------------------------------------------------"
    echo "-- Schema: ${CATALOG}.${SCHEMA}"
    echo "-- -----------------------------------------------------------"

    TABLES=$(databricks sql execute $PROFILE_FLAG \
      --statement "SHOW TABLES IN \`${CATALOG}\`.\`${SCHEMA}\`" \
      --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for row in data.get('result', {}).get('data_array', []):
    print(row[1] if isinstance(row, list) else row)
" 2>/dev/null || echo "")

    if [[ -z "$TABLES" ]]; then
      echo "-- (no tables found or connection failed)"
      echo ""
      continue
    fi

    for TABLE in $TABLES; do
      echo ""
      echo "-- Table: ${CATALOG}.${SCHEMA}.${TABLE}"
      DDL=$(databricks sql execute $PROFILE_FLAG \
        --statement "SHOW CREATE TABLE \`${CATALOG}\`.\`${SCHEMA}\`.\`${TABLE}\`" \
        --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
rows = data.get('result', {}).get('data_array', [])
if rows:
    print(rows[0][0] if isinstance(rows[0], list) else rows[0])
" 2>/dev/null || echo "-- ERROR: could not retrieve DDL for ${CATALOG}.${SCHEMA}.${TABLE}")
      echo "$DDL;"
      echo ""
    done
  done
} > "$OUTPUT_FILE"

echo ""
echo "[OK] Metadata backup saved to: ${OUTPUT_FILE}"
echo "     Tables exported from catalog '${CATALOG}'"
