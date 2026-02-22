from typing import List, Optional
from datetime import datetime as dt
from logging import Logger

from utils.dm_redis import DMRedis


class APIKeysManager:
    """
    Gerencia a eleição e liberação de API keys usando Redis como semáforo distribuído.

    redis_semaphore (db=REDIS_DB_APK_SEMAPHORE) — hash por api_key : { process, last_update }
    redis_counter   (db=REDIS_DB_APK_COUNTER)   — hash por api_key : { num_req_1d, end }
    """

    def __init__(self, logger: Logger, pid: str, redis_semaphore: DMRedis, redis_counter: DMRedis, api_keys_compacted: str = None):
        self.logger = logger
        self.pid = pid
        self.redis_semaphore = redis_semaphore   # db=REDIS_DB_APK_SEMAPHORE
        self.redis_counter   = redis_counter     # db=REDIS_DB_APK_COUNTER
        self.api_keys = self._decompress_api_key_names(api_keys_compacted)
        self.logger.info(f"API KEYS: {self.api_keys}")
        self.logger.info("API Keys Manager configured")

    def _decompress_api_key_names(self, api_keys_compacted: str) -> List[str]:
        """Ex: 'infura-api-key-1-4' → ['infura-api-key-1', ..., 'infura-api-key-4']"""
        interval = [int(i) for i in api_keys_compacted.split("-")[-2:]]
        name_secret = "-".join(api_keys_compacted.split("-")[:-2])
        return [f"{name_secret}-{i}" for i in range(interval[0], interval[1] + 1)]

    def check_api_key_request(self, api_key: str) -> None:
        """Registra/atualiza a posse da api_key neste processo no semáforo."""
        self.redis_semaphore.hset(api_key, mapping={"process": self.pid, "last_update": dt.now().timestamp()})

    def check_if_api_key_is_mine(self, api_key_name: str) -> bool:
        """Retorna True se este processo ainda detém a api_key no semáforo."""
        return self.redis_semaphore.hget(api_key_name, "process") == self.pid

    def release_api_key_from_semaphore(self, actual_api_key: str) -> None:
        """Libera a api_key do semáforo."""
        self.redis_semaphore.delete(actual_api_key)

    def free_api_keys(self, free_timeout: float = 15) -> None:
        """Libera chaves cujo last_update seja mais antigo que free_timeout segundos."""
        held_keys = self.redis_semaphore.keys()
        if not held_keys:
            return
        for api_key in held_keys:
            data = self.redis_semaphore.hgetall(api_key)
            if data and dt.now().timestamp() - float(data.get("last_update", 0)) > free_timeout:
                self.redis_semaphore.delete(api_key)
                self.logger.info(f"API KEY FREE: {api_key}")

    def get_keys_sorted_by_consumption(self) -> List[str]:
        """Retorna api_keys da menos para a mais utilizada, priorizando as sem histórico."""
        consumed_keys = self.redis_counter.keys()
        data = [{"name": k, **self.redis_counter.hgetall(k)} for k in consumed_keys]
        infura_data = [(x["name"], int(x.get("num_req_1d", 0)), x.get("end", ""))
                       for x in data if "infura" in x["name"]]
        infura_sorted = sorted(infura_data, key=lambda x: (x[2], x[1]))
        known_keys = [k[0] for k in infura_sorted]
        missing = [k for k in self.api_keys if k not in known_keys]
        return missing + known_keys

    def elect_new_api_key(self) -> Optional[str]:
        """Elege a api_key menos utilizada que ainda não esteja no semáforo."""
        available_sorted = self.get_keys_sorted_by_consumption()
        held_keys = self.redis_semaphore.keys()
        for api_key in available_sorted:
            if api_key not in held_keys:
                self.logger.info(f"API KEY ELECTED: {api_key}")
                return api_key
        return None
