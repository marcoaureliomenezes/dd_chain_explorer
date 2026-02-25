"""
utils_decode/abi_cache.py

Cache de ABIs de contratos Ethereum usando Redis (DB 6).

Estrutura no Redis:
  Hash   "contract_abis"        → { address: abi_json }  (sem TTL — ABIs são imutáveis)
  String "abi:nv:{address}"     → "1"  com TTL 24h        (negative cache — contrato não verificado)

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

from utils.dm_redis import DMRedis


_HASH_KEY           = "contract_abis"
_UNVERIFIED_PREFIX  = "abi:nv:"
_DEFAULT_DB         = 6
_DEFAULT_NV_TTL     = 86_400   # 24 h


class ABICache:
    """Cache persistente de ABIs em Redis DB 6."""

    def __init__(
        self,
        logger: logging.Logger,
        redis_db: int = _DEFAULT_DB,
        unverified_ttl: int = _DEFAULT_NV_TTL,
    ):
        self.logger = logger
        self._redis = DMRedis(db=redis_db, logger=logger)
        self._nv_ttl = unverified_ttl

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
        if self._redis.exists(f"{_UNVERIFIED_PREFIX}{address}"):
            return None

        abi_json = self._redis.hget(_HASH_KEY, address)
        if abi_json is not None:
            try:
                return json.loads(abi_json)
            except (json.JSONDecodeError, TypeError):
                self.logger.warning(f"[ABICache] Corrupt entry for {address}, removing.")
                self._redis.hdel(_HASH_KEY, address)
        return None

    def put(self, address: str, abi: list) -> None:
        """Armazena ABI permanentemente (ABIs nunca mudam)."""
        address = address.lower()
        self._redis.hset(_HASH_KEY, key=address, value=json.dumps(abi))
        # Remove negative cache se existir
        self._redis.delete(f"{_UNVERIFIED_PREFIX}{address}")

    def mark_unverified(self, address: str) -> None:
        """
        Registra que o endereço não possui ABI verificada.

        Usa TTL para que re-tentemos após ``unverified_ttl`` segundos
        (o dono do contrato pode verificar o código posteriormente).
        """
        address = address.lower()
        self._redis.set(f"{_UNVERIFIED_PREFIX}{address}", "1", ex=self._nv_ttl)

    def is_unverified(self, address: str) -> bool:
        """True se o endereço está no negative cache."""
        return self._redis.exists(f"{_UNVERIFIED_PREFIX}{address.lower()}") > 0

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        cached_abis = len(self._redis.raw_client.hkeys(_HASH_KEY))
        unverified  = len(self._redis.keys(f"{_UNVERIFIED_PREFIX}*"))
        return {"cached_abis": cached_abis, "unverified_addresses": unverified}

    def ping(self) -> bool:
        """Healthcheck — verifica conectividade com Redis."""
        return self._redis.ping()
