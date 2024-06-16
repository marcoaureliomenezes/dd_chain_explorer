#!/bin/bash

mkdir -p ./docker/app_layer

cd ./docker/app_layer && \
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-stream-txs.git && \
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-watchers.git && \
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-actors.git && \
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-monitor.git
