"""
dm_redis.py

Wrapper para conexão Redis adaptável por ambiente (APP_ENV).

Comportamento:
  APP_ENV=dev  → Redis local (container), sem TLS, sem senha
  APP_ENV=prod → ElastiCache Redis (AWS), TLS obrigatório, auth token opcional

Variáveis de ambiente esperadas:
  APP_ENV           : 'dev' ou 'prod'
  REDIS_HOST        : hostname do Redis (container 'redis' em DEV, endpoint ElastiCache em PROD)
  REDIS_PORT        : porta (padrão 6379 em DEV, 6380 em PROD com TLS)
  REDIS_PASSWORD    : auth token (vazio em DEV, token ElastiCache em PROD)

Uso:
    cache = DMRedis(db=2, logger=LOGGER)
    cache.set("block:100", "0xabc")
    val  = cache.get("block:100")
    cache.delete("block:100")
"""

import logging
import os
from typing import Any, Dict, List, Mapping, Optional, Union

from redis import Redis
from redis.exceptions import RedisError


class DMRedis:
    """
    Cliente Redis reutilizável — DEV usa Redis local, PROD usa ElastiCache com TLS.

    Parameters
    ----------
    db        : Índice do banco Redis (0-15). Cada caso de uso usa um db distinto para
                isolamento:  0 = semáforo de API keys  |  1 = contador API keys  |  2 = cache de blocos
    logger    : Logger externo; se None cria um interno.
    """

    def __init__(
        self,
        db: int = 0,
        logger: Optional[logging.Logger] = None,
    ):
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

        app_env     = os.getenv("APP_ENV", "prod").lower()
        host        = os.getenv("REDIS_HOST", "localhost")
        port        = int(os.getenv("REDIS_PORT", "6379"))
        password    = os.getenv("REDIS_PASSWORD") or None  # None → sem autenticação

        if app_env == "dev":
            self._client = Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
            )
        else:
            # ElastiCache Redis com TLS (in-transit encryption obrigatório em PROD)
            # ssl_cert_reqs=None → não valida certificado (adequado para ElastiCache sem CA customizada)
            self._client = Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                ssl=True,
                ssl_cert_reqs=None,
                decode_responses=True,
            )

        self.logger.info(f"DMRedis | env={app_env} | host={host}:{port} | db={db}")

    # ------------------------------------------------------------------
    # Strings
    # ------------------------------------------------------------------

    def set(self, name: str, value: Any, ex: Optional[int] = None) -> None:
        """SET — armazena valor. ex = TTL em segundos (opcional)."""
        self._client.set(name, value, ex=ex)

    def get(self, name: str) -> Optional[str]:
        """GET — retorna valor ou None."""
        return self._client.get(name)

    def delete(self, *names: str) -> int:
        """DEL — remove uma ou mais chaves. Retorna número de chaves deletadas."""
        return self._client.delete(*names)

    def exists(self, *names: str) -> int:
        """EXISTS — retorna o número de chaves existentes entre as fornecidas."""
        return self._client.exists(*names)

    def expire(self, name: str, time: int) -> bool:
        """EXPIRE — define TTL em segundos para uma chave."""
        return self._client.expire(name, time)

    def keys(self, pattern: str = "*") -> List[str]:
        """KEYS — retorna todas as chaves que correspondem ao padrão."""
        return self._client.keys(pattern)

    # ------------------------------------------------------------------
    # Hashes
    # ------------------------------------------------------------------

    def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Mapping[str, Any]] = None,
    ) -> int:
        """HSET — define um ou vários campos de um hash."""
        return self._client.hset(name, key=key, value=value, mapping=mapping)

    def hget(self, name: str, key: str) -> Optional[str]:
        """HGET — retorna o valor de um campo de um hash."""
        return self._client.hget(name, key)

    def hgetall(self, name: str) -> Dict[str, str]:
        """HGETALL — retorna todos os campos de um hash."""
        return self._client.hgetall(name)

    def hdel(self, name: str, *keys: str) -> int:
        """HDEL — remove campos de um hash."""
        return self._client.hdel(name, *keys)

    # ------------------------------------------------------------------
    # Sets
    # ------------------------------------------------------------------

    def sadd(self, name: str, *values: Any) -> int:
        """SADD — adiciona membros a um set."""
        return self._client.sadd(name, *values)

    def smembers(self, name: str) -> set:
        """SMEMBERS — retorna todos os membros de um set."""
        return self._client.smembers(name)

    def srem(self, name: str, *values: Any) -> int:
        """SREM — remove membros de um set."""
        return self._client.srem(name, *values)

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Verifica conectividade. Retorna True se OK."""
        try:
            return self._client.ping()
        except RedisError as e:
            self.logger.error(f"DMRedis | ping failed: {e}")
            return False

    @property
    def raw_client(self) -> Redis:
        """Retorna o cliente Redis subjacente para uso avançado."""
        return self._client
