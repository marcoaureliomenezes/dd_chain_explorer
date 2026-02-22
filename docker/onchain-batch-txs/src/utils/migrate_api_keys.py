"""
migrate_api_keys.py
====================
Migra API keys do Azure Key Vault para o AWS SSM Parameter Store.

Lógica:
- Lê todas as chaves habilitadas do Azure Key Vault.
- Lê todos os parâmetros existentes no SSM Parameter Store.
- Para cada chave do Key Vault cujo VALOR ainda não está no SSM,
  cria um novo parâmetro SecureString no SSM usando o mesmo nome
  (ou um sufixo numérico disponível se o nome já estiver ocupado
  por um valor diferente).

Uso:
    python migrate_api_keys.py \
        --vault-name  DataMasterNodeAsAService \
        --region      sa-east-1 \
        [--dry-run]

Flags:
    --dry-run   Exibe o que seria feito sem criar nada no SSM.
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate_api_keys")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_and_number(name: str) -> tuple[str, int]:
    """
    Separa o sufixo numérico de um nome.

    Ex: 'infura-api-key-5' → ('infura-api-key', 5)
        'alchemy-api-key-12' → ('alchemy-api-key', 12)
    """
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1])
    return name, 0


def _next_available_name(base: str, existing_names: set[str]) -> str:
    """
    Retorna o próximo nome disponível para *base* que não esteja em *existing_names*.

    Ex: base='infura-api-key', existing={'infura-api-key-1', ..., 'infura-api-key-4'}
        → 'infura-api-key-5'
    """
    n = 1
    while True:
        candidate = f"{base}-{n}"
        if candidate not in existing_names:
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Core migration
# ---------------------------------------------------------------------------

def migrate(
    vault_name: str,
    region: str,
    dry_run: bool = False,
) -> None:

    # --- Importa os clientes (devem estar no mesmo diretório ou no PYTHONPATH) ---
    try:
        from dm_key_vault import KeyVaultClient
        from dm_parameter_store import ParameterStoreClient
    except ImportError:
        # Tenta import relativo quando executado a partir do projeto
        import importlib, os, sys
        sys.path.insert(0, os.path.dirname(__file__))
        from dm_key_vault import KeyVaultClient
        from dm_parameter_store import ParameterStoreClient

    # --- 1. Lê todas as chaves do Azure Key Vault ---
    logger.info(f"Conectando ao Key Vault '{vault_name}'…")
    kv_client = KeyVaultClient(vault_name=vault_name)
    akv_secrets: dict[str, str] = kv_client.list_secrets()
    logger.info(f"  {len(akv_secrets)} segredos lidos do Key Vault.")

    if not akv_secrets:
        logger.warning("Nenhum segredo encontrado no Key Vault. Encerrando.")
        return

    # --- 2. Lê todos os parâmetros do SSM ---
    logger.info(f"Conectando ao SSM Parameter Store (region={region})…")
    ssm_client = ParameterStoreClient(region_name=region)
    ssm_params: dict[str, str] = ssm_client.list_parameters()
    logger.info(f"  {len(ssm_params)} parâmetros lidos do SSM.")

    # Índice invertido: valor → nome (para detectar duplicatas por valor)
    ssm_value_to_name: dict[str, str] = {v: k for k, v in ssm_params.items()}
    ssm_names: set[str] = set(ssm_params.keys())

    # --- 3. Compara e migra ---
    created = 0
    skipped_already_exist = 0
    skipped_errors = 0

    for akv_name, akv_value in sorted(akv_secrets.items()):
        # Chave cujo VALOR já existe no SSM → pula (já migrada)
        if akv_value in ssm_value_to_name:
            existing_ssm_name = ssm_value_to_name[akv_value]
            logger.info(
                f"  SKIP  {akv_name!r:35s} → valor já em SSM como {existing_ssm_name!r}"
            )
            skipped_already_exist += 1
            continue

        # Determina o nome a usar no SSM
        if akv_name not in ssm_names:
            # Nome livre → usa o mesmo nome do Key Vault
            target_name = akv_name
        else:
            # Nome ocupado por outro valor → gera próximo número disponível
            base, _ = _base_and_number(akv_name)
            target_name = _next_available_name(base, ssm_names)
            logger.warning(
                f"  Nome {akv_name!r} já existe no SSM com valor diferente. "
                f"Usando {target_name!r}."
            )

        action_label = "[DRY-RUN] WOULD CREATE" if dry_run else "CREATE"
        logger.info(f"  {action_label}  {akv_name!r:35s} → SSM: {target_name!r}")

        if not dry_run:
            ok = ssm_client.put_parameter(
                name=target_name,
                value=akv_value,
                description=f"Migrado do Azure Key Vault '{vault_name}' (origem: {akv_name})",
                overwrite=False,
            )
            if ok:
                # Atualiza os índices locais para evitar colisões no mesmo run
                ssm_names.add(target_name)
                ssm_params[target_name] = akv_value
                ssm_value_to_name[akv_value] = target_name
                created += 1
            else:
                skipped_errors += 1
        else:
            # Em dry-run apenas registra
            ssm_names.add(target_name)
            created += 1

    # --- 4. Resumo ---
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migração concluída.")
    logger.info(f"  Criados no SSM  : {created}")
    logger.info(f"  Já existiam     : {skipped_already_exist}")
    logger.info(f"  Erros           : {skipped_errors}")
    if dry_run:
        logger.info("  (modo dry-run — nenhuma chave foi realmente criada)")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migra API keys do Azure Key Vault para o AWS SSM Parameter Store."
    )
    parser.add_argument(
        "--vault-name",
        required=True,
        help="Nome do Azure Key Vault. Ex: DataMasterNodeAsAService",
    )
    parser.add_argument(
        "--region",
        default="sa-east-1",
        help="Região AWS do SSM Parameter Store. (default: sa-east-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a migração sem criar nada no SSM.",
    )
    args = parser.parse_args()

    migrate(
        vault_name=args.vault_name,
        region=args.region,
        dry_run=args.dry_run,
    )
