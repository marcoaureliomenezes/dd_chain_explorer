"""
dm_chain_utils — shared utilities for dd_chain_explorer Docker applications.
"""

from dm_chain_utils.api_keys_manager import APIKeysManager
from dm_chain_utils.dm_dynamodb import DMDynamoDB
from dm_chain_utils.dm_etherscan import EtherscanClient
from dm_chain_utils.dm_kafka_admin import KafkaAdminClient
from dm_chain_utils.dm_kafka_client import KafkaHandler
from dm_chain_utils.dm_logger import KafkaLoggingHandler, ConsoleLoggingHandler
from dm_chain_utils.dm_parameter_store import ParameterStoreClient
from dm_chain_utils.dm_schema_reg_client import get_schema
from dm_chain_utils.dm_web3_client import Web3Handler

__version__ = "1.1.0"
__all__ = [
    "APIKeysManager",
    "DMDynamoDB",
    "EtherscanClient",
    "KafkaAdminClient",
    "KafkaHandler",
    "KafkaLoggingHandler",
    "ConsoleLoggingHandler",
    "ParameterStoreClient",
    "get_schema",
    "Web3Handler",
]
