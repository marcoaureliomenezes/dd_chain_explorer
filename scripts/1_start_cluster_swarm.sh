#!/bin/bash

IP_MANAGER=192.168.15.88
NODE_WORKER_1=dadaia@192.168.15.8
NODE_WORKER_2=dadaia-server@192.168.15.83


init_docker_swarm() {
  join_cluster_command=$(docker swarm init --advertise-addr ${IP_MANAGER} 2>/dev/null | grep "docker swarm join --token")
  if [ $? -eq 0 ]; then
    echo "Cluster Docker Swarm inicializado com sucesso!"
  else
    echo "Master já pertence a um cluster Docker Swarm!"
    join_cluster_command=$(docker swarm join-token manager | grep "docker swarm join --token")
    if [ $? -eq 0 ]; then
      echo "SUCCESS"
    else
      docker swarm leave --force
      join_cluster_command=$(docker swarm init --advertise-addr ${IP_MANAGER} 2>/dev/null | grep "docker swarm join --token")

    fi
  fi
}

join_node() {
  HOST_MEU=$1
  COMMAND=$2
  echo "HOST para SSH: $HOST_MEU"
  echo "Executando comando: $COMMAND"
  ssh $HOST_MEU "docker swarm leave --force"
  ssh $HOST_MEU $COMMAND
}

echo $IP_MANAGER

init_docker_swarm
echo $join_cluster_command



join_node "$NODE_WORKER_1" "$join_cluster_command"
join_node "$NODE_WORKER_2" "$join_cluster_command"
#join_node "$NODE_WORKER_3" "$join_cluster_command"
