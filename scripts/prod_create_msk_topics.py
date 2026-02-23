#!/usr/bin/env python3
"""
Create all required Kafka topics on MSK for the chain explorer pipeline.

Usage:
    python3 scripts/prod_create_msk_topics.py [--brokers <bootstrap-servers>]

If --brokers is not provided, fetches from AWS MSK API using --cluster-name.
"""

import argparse
import logging
import sys
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("topic-setup")

# --------------------------------------------------------------------------
# Topic definitions: (name, partitions, replication_factor, configs)
# --------------------------------------------------------------------------
TOPICS = [
    # Application logs
    ("mainnet.0.application.logs",          4,  2, {"retention.ms": "86400000"}),  # 1 day
    # Mined blocks events (fast lane)
    ("mainnet.1.mined_blocks.events",       4,  2, {"retention.ms": "86400000"}),
    # Full block data
    ("mainnet.2.blocks.data",               4,  2, {"retention.ms": "604800000"}), # 7 days
    # Transaction hash IDs (fan-out with 8 partitions for crawler parallelism)
    ("mainnet.3.block.txs.hash_id",         8,  2, {"retention.ms": "86400000"}),
    # Full transaction data
    ("mainnet.4.transactions.data",         4,  2, {"retention.ms": "604800000"}),
    # Decoded transaction inputs
    ("mainnet.5.transactions.input_decoded", 4, 2, {"retention.ms": "604800000"}),
]


def get_msk_brokers(cluster_name: str, region: str) -> str:
    client = boto3.client("kafka", region_name=region)
    clusters = client.list_clusters(ClusterNameFilter=cluster_name)["ClusterInfoList"]
    if not clusters:
        raise ValueError(f"MSK cluster '{cluster_name}' not found in region {region}")
    cluster_arn = clusters[0]["ClusterArn"]
    bs = client.get_bootstrap_brokers(ClusterArn=cluster_arn)
    brokers = bs.get("BootstrapBrokerString") or bs.get("BootstrapBrokerStringSaslIam")
    logger.info(f"MSK bootstrap brokers: {brokers}")
    return brokers


def create_topics(brokers: str) -> None:
    try:
        from confluent_kafka.admin import AdminClient, NewTopic
    except ImportError:
        logger.error("confluent_kafka not installed. Run: pip install confluent-kafka")
        sys.exit(1)

    admin = AdminClient({"bootstrap.servers": brokers})

    # List existing topics
    existing = set(admin.list_topics().topics.keys())
    logger.info(f"Existing topics: {sorted(t for t in existing if not t.startswith('_'))}")

    new_topics = []
    for name, partitions, replication, configs in TOPICS:
        if name in existing:
            logger.info(f"  SKIP  {name} (already exists)")
        else:
            logger.info(f"  CREATE {name} (partitions={partitions}, replication={replication})")
            new_topics.append(NewTopic(name, partitions, replication, config=configs))

    if not new_topics:
        logger.info("All topics already exist.")
        return

    results = admin.create_topics(new_topics)
    for name, future in results.items():
        try:
            future.result()
            logger.info(f"  OK    {name}")
        except Exception as e:
            logger.error(f"  FAIL  {name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Create MSK Kafka topics for chain explorer pipeline")
    parser.add_argument("--brokers", help="Kafka bootstrap servers (overrides --cluster-name)")
    parser.add_argument("--cluster-name", default="dm-chain-explorer-msk", help="MSK cluster name")
    parser.add_argument("--region", default="sa-east-1", help="AWS region")
    args = parser.parse_args()

    brokers = args.brokers
    if not brokers:
        logger.info(f"Fetching MSK brokers for cluster '{args.cluster_name}' in {args.region}")
        brokers = get_msk_brokers(args.cluster_name, args.region)

    create_topics(brokers)


if __name__ == "__main__":
    main()
