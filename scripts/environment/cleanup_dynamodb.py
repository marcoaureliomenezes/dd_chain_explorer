#!/usr/bin/env python3
"""
Deleta todos os itens de uma tabela DynamoDB.

Substitui: dag_eventual_2_delete_environment.py (parte DynamoDB)

Uso:
    python scripts/environment/cleanup_dynamodb.py --table-name dm-chain-explorer
    python scripts/environment/cleanup_dynamodb.py --table-name dm-chain-explorer --dry-run
"""

import argparse
import sys

import boto3


def delete_all_items(table_name: str, dry_run: bool = False) -> int:
    """Scan + batch delete all items from a DynamoDB table. Returns count."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Get key schema to know which attributes form the primary key
    key_attrs = [k["AttributeName"] for k in table.key_schema]
    deleted = 0

    scan_kwargs = {"ProjectionExpression": ", ".join(key_attrs)}
    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])

        if not items:
            break

        if dry_run:
            for item in items:
                print(f"[DRY-RUN] Would delete: {item}")
            deleted += len(items)
        else:
            with table.batch_writer() as batch:
                for item in items:
                    key = {k: item[k] for k in key_attrs}
                    batch.delete_item(Key=key)
                    deleted += 1

        # Continue scanning if there are more items
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return deleted


def main():
    parser = argparse.ArgumentParser(description="Delete all items from a DynamoDB table")
    parser.add_argument("--table-name", required=True, help="DynamoDB table name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List items without deleting",
    )
    args = parser.parse_args()

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Cleaning table: {args.table_name}")
    count = delete_all_items(args.table_name, dry_run=args.dry_run)
    print(f"{'[DRY-RUN] Would delete' if args.dry_run else 'Deleted'}: {count} items")


if __name__ == "__main__":
    main()
