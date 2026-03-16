from typing import List, Optional
from datetime import datetime as dt
from logging import Logger

from dm_chain_utils.dm_dynamodb import DMDynamoDB


class APIKeysManager:
    """
    Gerencia a eleição e liberação de API keys usando DynamoDB como semáforo distribuído.

    Tabela single-table "dm-chain-explorer":
      PK="SEMAPHORE"  SK="{api_key_name}"  → { process, last_update, ttl }
      PK="COUNTER"    SK="{api_key_name}"  → { num_req_1d, start, end, last_req }
    """

    SEMAPHORE_PK = "SEMAPHORE"
    COUNTER_PK = "COUNTER"
    SEMAPHORE_TTL = 60  # seconds — itens expiram automaticamente via DynamoDB TTL

    def __init__(self, logger: Logger, pid: str, dynamodb: DMDynamoDB, api_keys_compacted: str = None):
        self.logger = logger
        self.pid = pid
        self.dynamodb = dynamodb
        self.api_keys = self._decompress_api_key_names(api_keys_compacted)
        self.logger.info(f"API KEYS: {self.api_keys}")
        self.logger.info("API Keys Manager configured (DynamoDB)")

    def _decompress_api_key_names(self, api_keys_compacted: str) -> List[str]:
        """Ex: 'infura-api-key-1-4' → ['infura-api-key-1', ..., 'infura-api-key-4']"""
        interval = [int(i) for i in api_keys_compacted.split("-")[-2:]]
        name_secret = "-".join(api_keys_compacted.split("-")[:-2])
        return [f"{name_secret}-{i}" for i in range(interval[0], interval[1] + 1)]

    def check_api_key_request(self, api_key: str) -> None:
        """Registra/atualiza a posse da api_key neste processo no semáforo."""
        self.dynamodb.put_item(
            self.SEMAPHORE_PK,
            api_key,
            attrs={"process": self.pid, "last_update": str(dt.now().timestamp())},
            ttl_seconds=self.SEMAPHORE_TTL,
        )

    def check_if_api_key_is_mine(self, api_key_name: str) -> bool:
        """Retorna True se este processo ainda detém a api_key no semáforo."""
        item = self.dynamodb.get_item(self.SEMAPHORE_PK, api_key_name)
        if item:
            return item.get("process") == self.pid
        return False

    def release_api_key_from_semaphore(self, actual_api_key: str) -> None:
        """Libera a api_key do semáforo."""
        self.dynamodb.delete_item(self.SEMAPHORE_PK, actual_api_key)

    def free_api_keys(self, free_timeout: float = 15) -> None:
        """Libera chaves cujo last_update seja mais antigo que free_timeout segundos."""
        held_items = self.dynamodb.query(self.SEMAPHORE_PK)
        if not held_items:
            return
        for item in held_items:
            last_update = float(item.get("last_update", 0))
            if dt.now().timestamp() - last_update > free_timeout:
                self.dynamodb.delete_item(self.SEMAPHORE_PK, item["sk"])
                self.logger.info(f"API KEY FREE: {item['sk']}")

    def get_keys_sorted_by_consumption(self) -> List[str]:
        """Retorna api_keys da menos para a mais utilizada, priorizando as sem histórico."""
        counter_items = self.dynamodb.query(self.COUNTER_PK)
        known_data = [
            (item["sk"], int(item.get("num_req_1d", 0)), item.get("end", ""))
            for item in counter_items if item["sk"] in self.api_keys
        ]
        known_sorted = sorted(known_data, key=lambda x: (x[2], x[1]))
        known_keys = [k[0] for k in known_sorted]
        missing = [k for k in self.api_keys if k not in known_keys]
        return missing + known_keys

    def elect_new_api_key(self) -> Optional[str]:
        """Elege a api_key menos utilizada que ainda não esteja no semáforo."""
        available_sorted = self.get_keys_sorted_by_consumption()
        held_keys = {item["sk"] for item in self.dynamodb.query(self.SEMAPHORE_PK)}
        for api_key in available_sorted:
            if api_key not in held_keys:
                self.logger.info(f"API KEY ELECTED: {api_key}")
                return api_key
        return None
