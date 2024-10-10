import json
import os
import time
from redis import StrictRedis


class RedisDisplay:

  def __init__(self, redis_client_out):
    self.redis_client_out = redis_client_out

  def show_semaphore(self, redis_client_in, key_name):
    keys = [key for key in redis_client_in.keys()]
    total = {key: redis_client_in.hgetall(key) for key in keys}
    for key in total:
      total[key] = {k: v for k, v in total[key].items()}
    self.redis_client_out.set(key_name, json.dumps(total))

if __name__ == "__main__":

  REDIS_HOST = os.getenv("REDIS_HOST")
  REDIS_PORT = os.getenv("REDIS_PORT")
  REDIS_PASS = os.getenv("REDIS_PASS")
  FREQ = float(os.getenv("FREQUENCY"))


  REDIS_CLIENT_IN_1 = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, decode_responses=True, db=0)
  REDIS_CLIENT_IN_2 = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, decode_responses=True, db=1)
  REDIS_CLIENT_OUT = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, decode_responses=True, db=2)

  redis_display = RedisDisplay(REDIS_CLIENT_OUT)

  while 1:

    redis_display.show_semaphore(REDIS_CLIENT_IN_1, "semaphore_1")
    redis_display.show_semaphore(REDIS_CLIENT_IN_2, "semaphore_2")
    
    time.sleep(FREQ)