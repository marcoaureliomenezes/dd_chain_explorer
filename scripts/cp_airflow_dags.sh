#!/bin/bash


cp -r ./mnt/airflow/dags ./docker/customized/airflow/mnt/
cp -r ./mnt/airflow/airflow.cfg ./docker/customized/airflow/mnt/

# stop and delete the container
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)