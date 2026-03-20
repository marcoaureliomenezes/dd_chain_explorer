#!/usr/bin/env python3
"""
Deleta todos os objetos S3 sob um determinado prefix.

Substitui: docker/onchain-batch-txs/src/s3_maintenance/1_delete_s3_objects.py
Substitui: dag_eventual_2_delete_environment.py (parte S3)

Uso:
    python scripts/environment/cleanup_s3.py --bucket dm-chain-explorer-dev-ingestion --prefix batch/
    python scripts/environment/cleanup_s3.py --bucket dm-chain-explorer-dev-ingestion --prefix batch/ --dry-run
"""

import argparse
import sys

import boto3


def delete_s3_objects(bucket: str, prefix: str, dry_run: bool = False) -> int:
    """Delete all objects under bucket/prefix. Returns count of deleted objects."""
    s3 = boto3.client("s3")
    deleted = 0
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = page.get("Contents", [])
        if not objects:
            continue

        keys = [{"Key": obj["Key"]} for obj in objects]

        if dry_run:
            for key in keys:
                print(f"[DRY-RUN] Would delete: s3://{bucket}/{key['Key']}")
            deleted += len(keys)
        else:
            resp = s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": keys, "Quiet": True},
            )
            errors = resp.get("Errors", [])
            if errors:
                for err in errors:
                    print(f"[ERROR] {err['Key']}: {err['Message']}", file=sys.stderr)
            deleted += len(keys) - len(errors)

    return deleted


def main():
    parser = argparse.ArgumentParser(description="Delete S3 objects by prefix")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--prefix", required=True, help="S3 key prefix to delete")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List objects without deleting",
    )
    args = parser.parse_args()

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Deleting s3://{args.bucket}/{args.prefix}*")
    count = delete_s3_objects(args.bucket, args.prefix, dry_run=args.dry_run)
    print(f"{'[DRY-RUN] Would delete' if args.dry_run else 'Deleted'}: {count} objects")


if __name__ == "__main__":
    main()
