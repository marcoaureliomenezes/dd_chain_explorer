"""
Schema Registry abstraction layer.

- APP_ENV=dev  → Confluent Schema Registry (local Docker, SCHEMA_REGISTRY_URL)
- APP_ENV=prod → AWS Glue Schema Registry (MSK, region sa-east-1)

Usage:
    from utils.dm_schema_reg_client import get_schema

    schema_str = get_schema(
        schema_name="mined-block-event-schema",
        schema_path="schemas/1_mined_block_event_schema_avro.json",  # used only in DEV to auto-register
    )
"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "dev")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")


# ---------------------------------------------------------------------------
# DEV — Confluent Schema Registry (REST API)
# ---------------------------------------------------------------------------

def _confluent_register_if_missing(subject: str, schema_path: str) -> None:
    """Register schema on Confluent SR if it does not exist yet."""
    check_url = f"{SCHEMA_REGISTRY_URL}/subjects/{subject}/versions/latest"
    r = requests.get(check_url, timeout=5)
    if r.status_code == 200:
        logger.info(f"[SchemaRegistry] Schema '{subject}' already registered.")
        return

    with open(schema_path) as f:
        schema_json = f.read()

    payload = {"schema": schema_json, "schemaType": "AVRO"}
    register_url = f"{SCHEMA_REGISTRY_URL}/subjects/{subject}/versions"
    r = requests.post(register_url, json=payload, timeout=5)
    r.raise_for_status()
    logger.info(f"[SchemaRegistry] Schema '{subject}' registered (id={r.json()['id']}).")


def _confluent_get_schema(subject: str, schema_path: str) -> str:
    """Get schema definition string from Confluent Schema Registry."""
    _confluent_register_if_missing(subject, schema_path)
    url = f"{SCHEMA_REGISTRY_URL}/subjects/{subject}/versions/latest"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()["schema"]


# ---------------------------------------------------------------------------
# PROD — AWS Glue Schema Registry
# ---------------------------------------------------------------------------

def _glue_get_schema(schema_name: str) -> str:
    """Get schema definition string from AWS Glue Schema Registry."""
    import boto3
    registry_name = os.getenv("GLUE_REGISTRY_NAME", "ChainExplorer-schema-registry")
    client = boto3.client("glue", region_name="sa-east-1")
    response = client.get_schema_version(
        SchemaId={
            "SchemaName": schema_name,
            "RegistryName": registry_name,
        },
        SchemaVersionNumber={"LatestVersion": True},
    )
    return response["SchemaDefinition"]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_schema(schema_name: str, schema_path: str | None = None) -> str:
    """
    Return the AVRO schema definition string for *schema_name*.

    Parameters
    ----------
    schema_name : str
        Name of the schema/subject (used as Confluent subject name and Glue schema name).
    schema_path : str, optional
        Path to the local .json file.  Required in DEV to auto-register the schema
        when it does not exist yet in the local Schema Registry.
    """
    if APP_ENV == "prod":
        logger.info(f"[SchemaRegistry] Fetching '{schema_name}' from AWS Glue (PROD).")
        return _glue_get_schema(schema_name)
    else:
        if schema_path is None:
            raise ValueError("schema_path is required in DEV (APP_ENV != 'prod').")
        logger.info(f"[SchemaRegistry] Fetching '{schema_name}' from Confluent SR (DEV).")
        return _confluent_get_schema(schema_name, schema_path)
