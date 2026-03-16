#!/usr/bin/env python3
"""
prod_ecs_logs.py
----------------
Obtém as últimas N linhas de logs de cada task ECS em execução no cluster
dm-chain-explorer-ecs via CloudWatch Logs.

Uso:
    python scripts/prod_ecs_logs.py [--lines 100] [--cluster dm-chain-explorer-ecs]
                                    [--service NOME] [--region sa-east-1]

Pré-requisitos:
    pip install boto3
    aws configure  (ou AWS_* env vars / IAM role)
"""

import argparse
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CLUSTER   = "dm-chain-explorer-ecs"
DEFAULT_LOG_GROUP = "/ecs/dm-chain-explorer"
DEFAULT_REGION    = "sa-east-1"
DEFAULT_LINES     = 100


def _fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def list_running_tasks(ecs, cluster: str, service_filter: str | None):
    """Return [(task_arn, service_name, container_name)] for running tasks."""
    paginator = ecs.get_paginator("list_tasks")
    task_arns = []
    kwargs = {"cluster": cluster, "desiredStatus": "RUNNING"}
    if service_filter:
        kwargs["serviceName"] = service_filter
    for page in paginator.paginate(**kwargs):
        task_arns.extend(page["taskArns"])

    if not task_arns:
        return []

    tasks = []
    # describe_tasks accepts max 100 at a time
    for i in range(0, len(task_arns), 100):
        resp = ecs.describe_tasks(cluster=cluster, tasks=task_arns[i:i+100])
        for t in resp["tasks"]:
            task_id   = t["taskArn"].split("/")[-1]
            # service name is in the group field: "service:dm-mined-blocks-watcher"
            group     = t.get("group", "")
            svc_name  = group.replace("service:", "") if group.startswith("service:") else group
            for c in t.get("containers", []):
                tasks.append((t["taskArn"], task_id, svc_name, c["name"]))
    return tasks


def get_log_stream(task_id: str, container_name: str) -> str:
    """Build the CloudWatch log stream name for a container."""
    # Stream format set by ECS awslogs driver: {prefix}/{container}/{task-id}
    return f"ecs/{container_name}/{task_id}"


def fetch_log_events(cw_logs, log_group: str, stream_name: str, n_lines: int) -> list[dict]:
    """Return the last n_lines events from a CloudWatch log stream."""
    try:
        resp = cw_logs.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            limit=n_lines,
            startFromHead=False,
        )
        return resp.get("events", [])
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            return []
        raise


def print_task_logs(task_id: str, svc_name: str, container: str,
                    events: list[dict], n_lines: int) -> None:
    width = 80
    header = f"  SERVICE: {svc_name}  |  TASK: {task_id[:12]}  |  CONTAINER: {container}  "
    print("\n" + "=" * width)
    print(header)
    print("=" * width)
    if not events:
        print("  (sem logs encontrados — stream pode não existir ainda)")
        return
    print(f"  Exibindo últimas {len(events)} / {n_lines} linhas solicitadas\n")
    for ev in events:
        ts  = _fmt_ts(ev["timestamp"])
        msg = ev["message"].rstrip()
        print(f"  [{ts}] {msg}")


def main():
    parser = argparse.ArgumentParser(description="Logs das tasks ECS em PROD")
    parser.add_argument("--cluster",   default=DEFAULT_CLUSTER,   help="Nome do cluster ECS")
    parser.add_argument("--log-group", default=DEFAULT_LOG_GROUP, help="CloudWatch log group")
    parser.add_argument("--service",   default=None,              help="Filtrar por serviço ECS (opcional)")
    parser.add_argument("--region",    default=DEFAULT_REGION,    help="Região AWS")
    parser.add_argument("--lines",     type=int, default=DEFAULT_LINES, help="Quantas linhas buscar por task")
    args = parser.parse_args()

    session  = boto3.Session(region_name=args.region)
    ecs      = session.client("ecs")
    cw_logs  = session.client("logs")

    print(f"\nCluster : {args.cluster}")
    print(f"Região  : {args.region}")
    print(f"Linhas  : {args.lines}")
    if args.service:
        print(f"Serviço : {args.service}")

    tasks = list_running_tasks(ecs, args.cluster, args.service)

    if not tasks:
        print("\nNenhuma task RUNNING encontrada.")
        sys.exit(0)

    print(f"\nTasks em execução: {len(tasks)}\n")

    for task_arn, task_id, svc_name, container in tasks:
        stream = get_log_stream(task_id, container)
        events = fetch_log_events(cw_logs, args.log_group, stream, args.lines)
        print_task_logs(task_id, svc_name, container, events, args.lines)

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
