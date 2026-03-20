"""
utils_decode/abi_cache.py

Cache de ABIs de contratos Ethereum usando DynamoDB (single-table design).

Estrutura no DynamoDB:
  PK="ABI"      SK="{address}" → { abi_json }              (sem TTL — ABIs são imutáveis)
  PK="ABI_NEG"  SK="{address}" → { checked_at, ttl }       (TTL 24h — negative cache)

Uso:
    from utils_decode.abi_cache import ABICache

    cache = ABICache(logger)
    abi   = cache.get("0xAbCd...")          # list | None
    cache.put("0xAbCd...", abi_list)        # armazena permanentemente
    cache.mark_unverified("0x1234...")      # negative cache 24h
"""

import json
import logging
from typing import Optional

from dm_chain_utils.dm_dynamodb import DMDynamoDB


_ABI_PK             = "ABI"
_ABI_NEG_PK         = "ABI_NEG"
_DEFAULT_NV_TTL     = 86_400   # 24 h


class ABICache:
    """Cache persistente de ABIs em DynamoDB (single-table)."""

    def __init__(
        self,
        logger: logging.Logger,
        unverified_ttl: int = _DEFAULT_NV_TTL,
        dynamodb: Optional[DMDynamoDB] = None,
        **kwargs,
    ):
        self.logger = logger
        self._nv_ttl = unverified_ttl
        self._db = dynamodb or DMDynamoDB(logger=logger)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, address: str) -> Optional[list]:
        """
        Busca a ABI no cache.

        Retorna a ABI como ``list`` (já parseada) ou ``None`` se não cached.
        Endereços no negative cache retornam ``None`` imediatamente.
        """
        address = address.lower()

        # Negative cache: contrato sabidamente não verificado
        if self._db.item_exists(_ABI_NEG_PK, address):
            return None

        item = self._db.get_item(_ABI_PK, address)
        if item is not None:
            abi_json = item.get("abi_json")
            if abi_json:
                try:
                    return json.loads(abi_json)
                except (json.JSONDecodeError, TypeError):
                    self.logger.warning(f"[ABICache] Corrupt entry for {address}, removing.")
                    self._db.delete_item(_ABI_PK, address)
        return None

    def put(self, address: str, abi: list) -> None:
        """Armazena ABI permanentemente (ABIs nunca mudam)."""
        address = address.lower()
        self._db.put_item(_ABI_PK, address, attrs={"abi_json": json.dumps(abi)})
        # Remove negative cache se existir
        self._db.delete_item(_ABI_NEG_PK, address)

    def mark_unverified(self, address: str) -> None:
        """
        Registra que o endereço não possui ABI verificada.

        Usa TTL para que re-tentemos após ``unverified_ttl`` segundos
        (o dono do contrato pode verificar o código posteriormente).
        """
        address = address.lower()
        self._db.put_item(
            _ABI_NEG_PK, address,
            attrs={"checked_at": "1"},
            ttl_seconds=self._nv_ttl,
        )

    def is_unverified(self, address: str) -> bool:
        """True se o endereço está no negative cache."""
        return self._db.item_exists(_ABI_NEG_PK, address.lower())

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        cached_abis = len(self._db.query(_ABI_PK))
        unverified = len(self._db.query(_ABI_NEG_PK))
        return {"cached_abis": cached_abis, "unverified_addresses": unverified}

    def ping(self) -> bool:
        """Healthcheck — verifica conectividade com DynamoDB."""
        return self._db.ping()
