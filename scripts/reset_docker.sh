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

