# Build context must be dd_chain_explorer/ (project root), not this folder.
# In DEV: docker compose sets context: ../../../  (== dd_chain_explorer/)
# In CI:  deploy_apps.yml sets context: dd_chain_explorer
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY docker/onchain-batch-txs/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install shared dm-chain-utils library
COPY utils/src/dm_chain_utils /app/dm_chain_utils

# Copy application source
COPY docker/onchain-batch-txs/src /app

ENTRYPOINT [ "sleep", "infinity" ]