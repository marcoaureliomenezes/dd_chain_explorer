#!/usr/bin/env python3
"""
prod_msk_metrics.py
-------------------
Avalia a saúde dos tópicos MSK e dos consumer groups via:
  • CloudWatch Metrics — throughput de bytes/mensagens por tópico
  • CloudWatch Logs    — logs de broker MSK (erros, rebalances)

Uso:
    python scripts/prod_msk_metrics.py [--cluster-name dm-chain-explorer-msk]
                                        [--region sa-east-1] [--minutes 30]

Pré-requisitos:
    pip install boto3
    aws configure  (ou AWS_* env vars / IAM role)
    MSK deve ter CloudWatch broker logs habilitado (já configurado no Terraform).
"""

import argparse
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CLUSTER_NAME = "dm-chain-explorer-msk"
DEFAULT_REGION       = "sa-east-1"
DEFAULT_MINUTES      = 30
MSK_LOG_GROUP        = "/aws/msk/dm-chain-explorer/broker-logs"

# Tópicos do pipeline de captura on-chain (mainnet)
PIPELINE_TOPICS = [
    "mainnet.0.application.logs",
    "mainnet.1.mined_blocks.events",
    "mainnet.2.blocks.data",
    "mainnet.3.block.txs.hash_id",
    "mainnet.4.transactions.data",
    "mainnet.5.transactions.input_decoded",
]

# Consumer groups registrados
CONSUMER_GROUPS = [
    "cg_orphan_block_events",
    "cg_block_data_crawler",
    "cg_mined_raw_txs",
    "cg_txs_input_decoder",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def get_cluster_arn(kafka_client, cluster_name: str) -> str | None:
    """Resolve cluster name → ARN."""
    paginator = kafka_client.get_paginator("list_clusters_v2")
    for page in paginator.paginate(ClusterNameFilter=cluster_name):
        for c in page.get("ClusterInfoList", []):
            if c["ClusterName"] == cluster_name:
                return c["ClusterArn"]
    return None


def get_broker_ids(kafka_client, cluster_arn: str) -> list[str]:
    """Return broker IDs for a given cluster ARN."""
    resp = kafka_client.list_nodes(ClusterArn=cluster_arn)
    return [str(n["BrokerNodeInfo"]["BrokerId"]) for n in resp.get("NodeInfoList", [])]


def fetch_metric(cw, namespace: str, metric_name: str, dimensions: list[dict],
                 start: datetime, end: datetime, period: int = 60) -> list[dict]:
    """Fetch CloudWatch metric datapoints (Average statistic)."""
    try:
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start,
            EndTime=end,
            Period=period,
            Statistics=["Average", "Sum"],
        )
        return sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
    except ClientError:
        return []


def avg_or_zero(datapoints: list[dict], key: str = "Average") -> float:
    if not datapoints:
        return 0.0
    return sum(d[key] for d in datapoints) / len(datapoints)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def section_cluster_info(kafka_client, cluster_arn: str, cluster_name: str) -> None:
    print("\n" + "=" * 70)
    print(f"  CLUSTER MSK: {cluster_name}")
    print(f"  ARN: {cluster_arn}")
    print("=" * 70)
    try:
        resp   = kafka_client.describe_cluster_v2(ClusterArn=cluster_arn)
        info   = resp["ClusterInfo"]
        state  = info.get("State", "?")
        created = info.get("CreationTime", "?")
        print(f"  Estado        : {state}")
        if created != "?":
            print(f"  Criado em     : {_fmt_ts(created)}")
        kafka_ver = info.get("Provisioned", {}).get("CurrentBrokerSoftwareInfo", {}).get("KafkaVersion", "?")
        n_brokers = info.get("Provisioned", {}).get("NumberOfBrokerNodes", "?")
        print(f"  Kafka version : {kafka_ver}")
        print(f"  Brokers       : {n_brokers}")
    except ClientError as e:
        print(f"  Erro ao descrever cluster: {e}")


def section_broker_metrics(cw, broker_ids: list[str], cluster_name: str,
                            start: datetime, end: datetime) -> None:
    print("\n" + "-" * 70)
    print(f"  MÉTRICAS DE BROKER  (últimos {int((end - start).total_seconds() // 60)} min)")
    print("-" * 70)

    for bid in broker_ids:
        dims = [
            {"Name": "Cluster Name", "Value": cluster_name},
            {"Name": "Broker ID",    "Value": bid},
        ]
        bytes_in  = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "BytesInPerSec",  dims, start, end))
        bytes_out = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "BytesOutPerSec", dims, start, end))
        msgs_in   = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "MessagesInPerSec", dims, start, end))
        cpu_sys   = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "CpuSystem", dims, start, end))
        cpu_usr   = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "CpuUser",   dims, start, end))
        mem_used  = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "MemoryUsed", dims, start, end))
        disk      = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "KafkaDataLogsDiskUsed", dims, start, end))

        print(f"\n  Broker {bid}:")
        print(f"    BytesInPerSec     : {bytes_in:>10.0f} B/s")
        print(f"    BytesOutPerSec    : {bytes_out:>10.0f} B/s")
        print(f"    MessagesInPerSec  : {msgs_in:>10.1f} msg/s")
        print(f"    CPU System        : {cpu_sys:>10.1f} %")
        print(f"    CPU User          : {cpu_usr:>10.1f} %")
        print(f"    Memory Used       : {mem_used:>10.0f} B")
        print(f"    Disk Used (logs)  : {disk:>10.1f} %")


def section_topic_metrics(cw, cluster_name: str, start: datetime, end: datetime) -> None:
    print("\n" + "-" * 70)
    print(f"  MÉTRICAS POR TÓPICO  (últimos {int((end - start).total_seconds() // 60)} min)")
    print("-" * 70)
    print(f"  {'Tópico':<46} {'Msgs/s':>8} {'BytesIn/s':>10} {'BytesOut/s':>11}")
    print(f"  {'-'*46} {'-'*8} {'-'*10} {'-'*11}")

    for topic in PIPELINE_TOPICS:
        dims = [
            {"Name": "Cluster Name", "Value": cluster_name},
            {"Name": "Topic",        "Value": topic},
        ]
        msgs_in   = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "MessagesInPerSec",  dims, start, end))
        bytes_in  = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "BytesInPerSec",     dims, start, end))
        bytes_out = avg_or_zero(fetch_metric(cw, "AWS/Kafka", "BytesOutPerSec",    dims, start, end))
        print(f"  {topic:<46} {msgs_in:>8.2f} {bytes_in:>10.0f} {bytes_out:>11.0f}")


def section_consumer_lag(cw, cluster_name: str, start: datetime, end: datetime) -> None:
    print("\n" + "-" * 70)
    print(f"  CONSUMER GROUP LAG  (últimos {int((end - start).total_seconds() // 60)} min)")
    print("-" * 70)
    print(f"  {'Consumer Group':<36} {'Topic':<46} {'Max Lag':>8}")
    print(f"  {'-'*36} {'-'*46} {'-'*8}")

    for cg in CONSUMER_GROUPS:
        for topic in PIPELINE_TOPICS:
            dims = [
                {"Name": "Cluster Name",    "Value": cluster_name},
                {"Name": "Consumer Group",  "Value": cg},
                {"Name": "Topic",           "Value": topic},
            ]
            lag_pts = fetch_metric(cw, "AWS/Kafka", "SumOffsetLag", dims, start, end)
            if lag_pts:
                max_lag = max(d.get("Average", 0) for d in lag_pts)
                print(f"  {cg:<36} {topic:<46} {max_lag:>8.0f}")


def section_broker_logs(cw_logs, minutes: int) -> None:
    print("\n" + "-" * 70)
    print(f"  LOGS DE BROKER MSK  (últimas {minutes} min — WARN/ERROR)")
    print("-" * 70)

    start_ms = int((datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)).timestamp() * 1000)

    try:
        # List log streams (one per broker per day)
        streams_resp = cw_logs.describe_log_streams(
            logGroupName=MSK_LOG_GROUP,
            orderBy="LastEventTime",
            descending=True,
            limit=10,
        )
        streams = [s["logStreamName"] for s in streams_resp.get("logStreams", [])]
    except ClientError as e:
        print(f"  Log group '{MSK_LOG_GROUP}' não encontrado: {e}")
        return

    if not streams:
        print("  Nenhum log stream encontrado.")
        return

    found_any = False
    for stream in streams:
        try:
            events_resp = cw_logs.filter_log_events(
                logGroupName=MSK_LOG_GROUP,
                logStreamNames=[stream],
                startTime=start_ms,
                filterPattern="?WARN ?ERROR ?FATAL ?Exception",
                limit=50,
            )
        except ClientError:
            continue

        events = events_resp.get("events", [])
        for ev in events:
            ts  = datetime.fromtimestamp(ev["timestamp"] / 1000, tz=timezone.utc)
            msg = ev["message"].rstrip()
            print(f"  [{_fmt_ts(ts)}] {msg}")
            found_any = True

    if not found_any:
        print("  Nenhum WARN/ERROR nos logs de broker no período.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Métricas e logs do cluster MSK em PROD")
    parser.add_argument("--cluster-name", default=DEFAULT_CLUSTER_NAME)
    parser.add_argument("--region",       default=DEFAULT_REGION)
    parser.add_argument("--minutes",      type=int, default=DEFAULT_MINUTES,
                        help="Janela de tempo em minutos para métricas CloudWatch")
    args = parser.parse_args()

    session  = boto3.Session(region_name=args.region)
    cw       = session.client("cloudwatch")
    cw_logs  = session.client("logs")
    kafka    = session.client("kafka")

    end   = datetime.now(tz=timezone.utc)
    start = end - timedelta(minutes=args.minutes)

    print(f"\n{'='*70}")
    print(f"  MSK HEALTH CHECK — {_fmt_ts(end)}")
    print(f"  Janela de análise: últimos {args.minutes} minutos")
    print(f"{'='*70}")

    cluster_arn = get_cluster_arn(kafka, args.cluster_name)
    if not cluster_arn:
        print(f"\nERRO: cluster '{args.cluster_name}' não encontrado na região {args.region}.")
        return

    section_cluster_info(kafka, cluster_arn, args.cluster_name)
    broker_ids = get_broker_ids(kafka, cluster_arn)
    section_broker_metrics(cw, broker_ids, args.cluster_name, start, end)
    section_topic_metrics(cw, args.cluster_name, start, end)
    section_consumer_lag(cw, args.cluster_name, start, end)
    section_broker_logs(cw_logs, args.minutes)

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
