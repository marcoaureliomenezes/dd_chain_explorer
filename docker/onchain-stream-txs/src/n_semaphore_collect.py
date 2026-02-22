import json
import logging
import os
import time

from utils.dm_redis import DMRedis


class RedisDisplay:

  def __init__(self, redis_client_out: DMRedis):
    self.redis_client_out = redis_client_out

  def show_semaphore(self, redis_client_in: DMRedis, key_name: str):
    keys = redis_client_in.keys("*")
    total = {key: redis_client_in.hgetall(key) for key in keys}
    self.redis_client_out.set(key_name, json.dumps(total))


if __name__ == "__main__":

  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
  logger = logging.getLogger("SEMAPHORE_DISPLAY")

  REDIS_DB_APK_SEMAPHORE     = int(os.getenv("REDIS_DB_APK_SEMAPHORE", 0))
  REDIS_DB_APK_COUNTER       = int(os.getenv("REDIS_DB_APK_COUNTER", 1))
  REDIS_DB_SEMAPHORE_DISPLAY = int(os.getenv("REDIS_DB_SEMAPHORE_DISPLAY", 3))
  FREQ = float(os.getenv("FREQUENCY", 5))

  redis_in_semaphore = DMRedis(db=REDIS_DB_APK_SEMAPHORE, logger=logger)
  redis_in_counter   = DMRedis(db=REDIS_DB_APK_COUNTER,   logger=logger)
  redis_out          = DMRedis(db=REDIS_DB_SEMAPHORE_DISPLAY, logger=logger)

  redis_display = RedisDisplay(redis_out)

  logger.info(f"Semaphore display started (in_db={REDIS_DB_APK_SEMAPHORE}/{REDIS_DB_APK_COUNTER}, out_db={REDIS_DB_SEMAPHORE_DISPLAY}, freq={FREQ}s)")

  while True:
    redis_display.show_semaphore(redis_in_semaphore, "semaphore_1")
    redis_display.show_semaphore(redis_in_counter,   "semaphore_2")
    time.sleep(FREQ)

    time.sleep(FREQ)