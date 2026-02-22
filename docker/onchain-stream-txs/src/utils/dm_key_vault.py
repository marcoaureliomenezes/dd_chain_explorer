"""
Azure Key Vault client.

Não utilizado em DEV (APP_ENV=dev). Disponível para integração futura
quando a aplicação precisar buscar segredos do Azure Key Vault.

Pré-requisito: pacotes azure-identity e azure-keyvault-secrets instalados.
  pip install azure-identity azure-keyvault-secrets

Uso:
    from utils.dm_key_vault import KeyVaultClient

    client = KeyVaultClient(vault_name="MyVaultName")
    api_key = client.get_secret("alchemy-api-key-1")
"""

import logging

logger = logging.getLogger(__name__)


class KeyVaultClient:

    def __init__(self, vault_name: str):
        """
        Parameters
        ----------
        vault_name : str
            Nome do Azure Key Vault (sem o domínio completo).
            A URL será montada como: https://{vault_name}.vault.azure.net/
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            self._vault_url = f"https://{vault_name}.vault.azure.net/"
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self._vault_url, credential=credential)
            logger.info(f"[KeyVault] Client initialized (vault='{vault_name}')")
        except ImportError:
            raise ImportError(
                "Pacotes Azure não instalados. Execute: "
                "pip install azure-identity azure-keyvault-secrets"
            )

    def get_secret(self, secret_name: str) -> str | None:
        """
        Busca um segredo no Azure Key Vault.

        Parameters
        ----------
        secret_name : str
            Nome do segredo no Key Vault.

        Returns
        -------
        str | None
            Valor do segredo, ou None em caso de erro.
        """
        try:
            secret = self._client.get_secret(secret_name)
            logger.info(f"[KeyVault] Retrieved: {secret_name}")
            return secret.value
        except Exception as e:
            logger.error(f"[KeyVault] Error fetching '{secret_name}': {e}")
            return None

    def list_secrets(self) -> dict[str, str]:
        """
        Lista todos os segredos habilitados no Key Vault e retorna seus valores.

        Returns
        -------
        dict[str, str]
            Mapeamento { nome_do_segredo: valor }, ignorando segredos desabilitados
            ou cujo valor não pôde ser lido.
        """
        secrets: dict[str, str] = {}
        try:
            for props in self._client.list_properties_of_secrets():
                if not props.enabled:
                    logger.debug(f"[KeyVault] Skipping disabled secret: {props.name}")
                    continue
                value = self.get_secret(props.name)
                if value is not None:
                    secrets[props.name] = value
        except Exception as e:
            logger.error(f"[KeyVault] Error listing secrets: {e}")
        logger.info(f"[KeyVault] Listed {len(secrets)} enabled secrets.")
        return secrets

    def delete_secret(self, secret_name: str) -> bool:
        """
        Inicia a exclusão de um segredo no Azure Key Vault.
        O segredo entra em estado 'soft-deleted' e pode ser recuperado dentro de 90 dias.

        Returns
        -------
        bool
            True em caso de sucesso, False em caso de erro.
        """
        try:
            poller = self._client.begin_delete_secret(secret_name)
            poller.result()  # aguarda conclusão
            logger.info(f"[KeyVault] Deleted: {secret_name}")
            return True
        except Exception as e:
            logger.error(f"[KeyVault] Error deleting '{secret_name}': {e}")
            return False
