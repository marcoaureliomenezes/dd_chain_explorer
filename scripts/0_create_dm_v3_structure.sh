#!/bin/bash

docker network create -d overlay --attachable vpc_kafka
# docker network create -d overlay --attachable layer_fast_prod
# docker network create -d overlay --attachable layer_ops_prod
