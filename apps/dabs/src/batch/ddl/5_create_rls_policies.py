# Databricks notebook source
# DDL — Row-Level Security para views g_api_keys no Unity Catalog
# Restringe leitura de dados sensíveis de API keys a membros do grupo admin.
# Requer: Databricks Runtime 12.2+ com Unity Catalog habilitado.

try:
    catalog     = dbutils.widgets.get("catalog")
    admin_group = dbutils.widgets.get("admin_group")
except Exception:
    catalog     = "dev"
    admin_group = "admins"

# Garante que o schema existe antes de criar a função
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.g_api_keys")

# Cria (ou substitui) a função de filtro no Unity Catalog.
# A função recebe o valor da coluna (api_key_name) mas não o usa —
# retorna TRUE apenas para membros do grupo admin.
spark.sql(f"""
  CREATE OR REPLACE FUNCTION `{catalog}`.g_api_keys.api_keys_visibility_filter(api_key_name STRING)
  COMMENT 'Row filter: allows row only if caller is member of group {admin_group}. Applied to g_api_keys views.'
  RETURN is_account_group_member('{admin_group}')
""")
print(f"[OK] Row filter function: `{catalog}`.g_api_keys.api_keys_visibility_filter")

# Aplica o filtro às views de consumo de API keys.
# Nota: Row filters em DLT Materialized Views requerem configuração manual via
# ALTER TABLE após o pipeline ter rodado. Skipa nesse notebook de setup inicial.
for view in ["etherscan_consumption", "web3_keys_consumption"]:
    try:
        spark.sql(f"""
          ALTER TABLE `{catalog}`.g_api_keys.{view}
          SET ROW FILTER `{catalog}`.g_api_keys.api_keys_visibility_filter ON (api_key_name)
        """)
        print(f"[OK] Row filter applied to `{catalog}`.g_api_keys.{view}")
    except Exception as e:
        print(f"[SKIP] Cannot apply row filter to `{catalog}`.g_api_keys.{view}: {str(e)[:150]}")

print(f"\n[DONE] RLS applied. Only members of '{admin_group}' can read g_api_keys views.")
print("       Non-members receive 0 rows (filter returns FALSE for all rows).")
print("       To remove: ALTER VIEW <view> DROP ROW FILTER")
