#!/bin/bash

echo "Deleting all Docker Images"
docker rmi $(docker images -q)

