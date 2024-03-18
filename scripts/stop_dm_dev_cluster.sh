#!/bin/bash


docker-compose -f services/cluster_dev_fast.yml down
docker-compose -f services/cluster_dev_batch.yml down
docker-compose -f services/cluster_dev_app.yml down