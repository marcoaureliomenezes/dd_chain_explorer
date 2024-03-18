#!/bin/bash


docker-compose -f services/cluster_dev_fast.yml up -d --build
docker-compose -f services/cluster_dev_batch.yml up -d --build
docker-compose -f services/cluster_dev_app.yml up -d

# Remove all volumes
