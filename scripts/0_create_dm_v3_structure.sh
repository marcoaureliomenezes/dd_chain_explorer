#!/bin/bash

docker network create -d overlay --attachable layer_batch_prod
docker network create -d overlay --attachable layer_fast_prod
docker network create -d overlay --attachable layer_ops_prod
