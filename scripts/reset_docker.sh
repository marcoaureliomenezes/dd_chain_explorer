#!/bin/bash

# Stop and remove all containers
docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)

# Delete all images
docker rmi $(docker images -q)

# Delete all networks
docker network rm $(docker network ls -q)

# Delete all volumes
docker volume rm $(docker volume ls -q)


for i in {1..6} ; do docker logs app-tx_processor-$i | tail -n 5 | grep API_request ; done


CONTAINER_ID=$(docker ps -a | grep scylladb | awk '{print $1}')