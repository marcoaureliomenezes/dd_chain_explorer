from typing import List
from datetime import datetime as dt

from redis import Redis
from logging import Logger


class APIKeysManager:

  def __init__(self, logger: Logger, pid: str, redis_client_1: Redis, redis_client_2: Redis, api_keys_compacted: List[str] = None):
    self.logger = logger
    self.pid = pid
    self.redis_client_1 = redis_client_1
    self.redis_client_2 = redis_client_2
    self.api_keys = self.decompress_api_key_names(api_keys_compacted)
    self.logger.info(f"API KEYS: {self.api_keys}")
    self.logger.info("API Keys Manager configured")


  def decompress_api_key_names(self, api_keys_compacted: str) -> List[str]:
    interval = [int(i) for i in api_keys_compacted.split("-")[-2:]]
    name_secret = "-".join(api_keys_compacted.split("-")[:-2])
    api_keys = [f"{name_secret}-{i}" for i in range(interval[0], interval[1] + 1)]
    return api_keys
  

  def get_keys_consume_from_redis(self) -> List[str]:
    data = [{"name": api_key, **self.redis_client_2.hgetall(api_key)} for api_key in self.redis_client_2.keys()]
    all_api_keys_data = list(map(lambda x: (x["name"], int(x["num_req_1d"]), x["end"]), data))
    infura_api_keys_data = filter(lambda x: "infura" in x[0], all_api_keys_data)
    api_keys_sorted = sorted(infura_api_keys_data, key=lambda x: (x[2], x[1]))
    missing_api_keys = list(set(self.api_keys) - set([api_key[0] for api_key in api_keys_sorted]))
    return missing_api_keys + [api_key[0] for api_key in api_keys_sorted]


  def elect_new_api_key(self) -> str:
    api_keys_consume = self.get_keys_consume_from_redis()
    api_keys_used = self.redis_client_1.keys()
    for api_key in api_keys_consume:
      if api_key not in api_keys_used:
        self.logger.info(f"API KEY ELECTED: {api_key}")
        return api_key
      
                     
  def free_api_keys(self, free_timeout: float = 15) -> None:
    if not self.redis_client_1.keys(): return
    print(self.redis_client_1.keys())
    api_keys_data_cached = {api_key: self.redis_client_1.hgetall(api_key) for api_key in self.redis_client_1.keys()}
    api_keys_to_free = [api_key for api_key, value in api_keys_data_cached.items() if dt.now().timestamp() - float(value["last_update"]) > free_timeout]
    for api_key in api_keys_to_free:
      self.redis_client_1.delete(api_key)
      self.logger.info(f"API KEY FREE: {api_key}")


  def check_api_key_request(self, api_key: str) -> None:
    self.redis_client_1.hset(api_key, mapping={"process": self.pid, "last_update":  dt.now().timestamp()})

  
  def check_if_api_key_is_mine(self, api_key_name: str) -> None:
    return self.redis_client_1.hget(api_key_name, "process") == self.pid


  def release_api_key_from_semaphore(self, actual_api_key: str) -> None:
    self.redis_client_1.delete(actual_api_key)



  