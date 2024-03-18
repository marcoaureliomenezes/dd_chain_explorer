#!/bin/bash


docker stack deploy -c services/cluster_prod_fast.yml layer_fast
# docker stack deploy -c services/cluster_prod_app.yml layer_app
# docker stack deploy -c services/cluster_prod_batch.yml layer_batch