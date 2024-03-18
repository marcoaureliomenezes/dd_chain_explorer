#!/bin/bash

docker build -t hadoop-base:latest ../docker/infra/hadoop/hadoop-base/
docker build -t hive-base:latest ../docker/infra/hive/hive-base/
docker build -t spark-base:latest ../docker/infra/spark/spark-base/

