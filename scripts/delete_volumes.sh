#!/bin/bash

# Delete all volumes

docker volume rm $(docker volume ls -q)