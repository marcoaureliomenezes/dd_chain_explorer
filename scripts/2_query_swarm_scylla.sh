#!/bin/bash

docker exec -it "$(docker ps -a | grep scylladb | awk '{print $1}')" cqlsh -e "select * from operations.api_keys_node_providers;"