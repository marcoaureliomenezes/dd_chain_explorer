#!/bin/bash

mkdir -p ./chain_explorer/layer_app

cd ./chain_explorer/app && \
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-stream-txs.git &&
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-watchers.git &&
      git clone git@github.com:Dadaia-s-Chain-Analyser/onchain-watchers.git
