

import docker
from docker import DockerClient
import os
from typing import Dict, List
import redis
import json
from datetime import datetime


class DockerHandler:

  def __init__(self):
    self.client: DockerClient = docker.from_env()

  def list_services(self):
    services = self.client.services.list()
    services = [service.name for service in services]
    return services

  def list_stack_services(self, stack_name):
    services = self.client.services.list(filters={"label": f"com.docker.stack.namespace={stack_name}"})
    services = [service.name for service in services]
    return services

  def restart_service(self, service_name):
    service = self.client.services.get(service_name)
    service.force_update()
    return
    
    

class SparkStreamingJobsHandler:
  
  def __init__(self):
    self.map_table_service = self.__get_map_table_service()
    self.docker_client = DockerHandler()

  def __get_map_table_service(self):
    return dict(
      newst_kafka_topics_multiplexed='layer_spark_apps_spark-app-multiplex-bronze',
      newst_mined_blocks_events='layer_spark_apps_spark-app-silver-mined-blocks-events',
      newst_apps_logs_fast='layer_spark_apps_spark-app-silver-logs',
      newst_blocks_fast='layer_spark_apps_spark-app-silver-blocks',
      newst_transactions_fast='layer_spark_apps_spark-app-silver-txs',
      newst_api_key_consumption_watcher='layer_spark_apps_spark-app-apk-comsumption'
    )
  
  def __get_redis_data_1(self) -> Dict[str, datetime]:
    redis_client = redis.Redis(os.getenv("REDIS_HOST"), os.getenv("REDIS_PORT"), 2, os.getenv("REDIS_PASS"), decode_responses=True)
    data = redis_client.get("semaphore_2")
    data = json.loads(data)
    last_req = max([i["last_req"] for i in data.values()])
    last_req = datetime.strptime(last_req, "%Y-%m-%d %H:%M:%S.%f")
    return {"newst_api_key_consumption_watcher": last_req}
  
  
  def __get_redis_data_5(self) -> Dict[str, datetime]:
    redis_client = redis.Redis(os.getenv("REDIS_HOST"), os.getenv("REDIS_PORT"), 5, os.getenv("REDIS_PASS"), decode_responses=True)
    redis_data = list(map(lambda key: (key, redis_client.get(key)), redis_client.keys()))
    redis_data_handled = {i: datetime.strptime(j, "%Y-%m-%d %H:%M:%S") for i, j in redis_data}
    return redis_data_handled
  

  def __get_tables_to_restart(self, redis_data_handled: Dict[str, datetime]) -> List[str]:
    data_delta = {i: (datetime.now() - j).total_seconds() for i, j in redis_data_handled.items()}
    data_late = {i: j for i, j in data_delta.items() if j > 900}
    tables_to_restart = list(data_late.keys())
    return tables_to_restart

    
  def __get_services_to_restart(self, tables_to_restart):
    services = self.docker_client.list_services()
    print("SERVICES ALL ", services)
    for service in tables_to_restart:
      service_name = self.map_table_service.get(service)
      if service_name:
        print(f"RESTARTING {service_name}")
        yield service_name


  def run(self) -> str:
    data_redis_1 = self.__get_redis_data_1()
    data_redis_5 = self.__get_redis_data_5()
    tables_to_restart = {**data_redis_1, **data_redis_5}
    tables_to_restart = self.__get_tables_to_restart(tables_to_restart)
    for service_to_restart in self.__get_services_to_restart(tables_to_restart):
      self.docker_client.restart_service(service_to_restart)
    return


