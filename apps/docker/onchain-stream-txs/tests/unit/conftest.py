"""
Hermetic test conftest: stub out every external import before job modules load.

This lets the 5 streaming job classes be imported without dm_chain_utils,
boto3, web3, or any network-requiring package being actually installed in the
test environment.

Strategy: inject fake modules into sys.modules BEFORE any job file is imported.
Because Python caches imports in sys.modules, the fakes replace the real packages
for the duration of the test session.
"""
import sys
import types
import logging
from unittest.mock import MagicMock


def _make_mock_module(name: str) -> types.ModuleType:
    """Return a module stub whose attributes are MagicMocks."""
    mod = types.ModuleType(name)
    mod.__spec__ = None  # silence pkgutil introspection warnings
    return mod


def _patch_external_imports() -> None:
    """Inject stub modules so job files can be imported hermetically."""

    # --- dm_chain_utils sub-modules ---
    stub_names = [
        "dm_chain_utils",
        "dm_chain_utils.dm_web3_client",
        "dm_chain_utils.dm_sqs",
        "dm_chain_utils.dm_cloudwatch_logger",
        "dm_chain_utils.dm_dynamodb",
        "dm_chain_utils.dm_firehose",
        "dm_chain_utils.dm_kinesis",
        "dm_chain_utils.dm_parameter_store",
        "dm_chain_utils.api_keys_manager",
    ]
    for name in stub_names:
        if name not in sys.modules:
            mod = _make_mock_module(name)
            # Attach each potential class as a MagicMock callable
            mod.Web3Handler = MagicMock
            mod.SQSHandler = MagicMock
            mod.CloudWatchLoggingHandler = MagicMock
            mod.DMDynamoDB = MagicMock
            mod.FirehoseHandler = MagicMock
            mod.KinesisHandler = MagicMock
            mod.ParameterStoreClient = MagicMock
            mod.APIKeysManager = MagicMock
            sys.modules[name] = mod

    # --- utils_decode (job 5 specific) ---
    for name in ("utils_decode", "utils_decode.abi_cache", "utils_decode.etherscan_multi"):
        if name not in sys.modules:
            mod = _make_mock_module(name)
            mod.ABICache = MagicMock
            mod.MultiKeyEtherscanClient = MagicMock
            sys.modules[name] = mod

    # --- web3 (job 5 imports Web3 directly) ---
    if "web3" not in sys.modules:
        mod = _make_mock_module("web3")
        web3_mock = MagicMock()
        web3_mock.to_checksum_address = lambda addr: addr
        mod.Web3 = MagicMock(return_value=web3_mock)
        mod.Web3.to_checksum_address = staticmethod(lambda addr: addr)
        sys.modules["web3"] = mod

    # --- eth_abi ---
    if "eth_abi" not in sys.modules:
        mod = _make_mock_module("eth_abi")
        mod.decode = MagicMock(return_value=[])
        sys.modules["eth_abi"] = mod

    # --- requests ---
    if "requests" not in sys.modules:
        mod = _make_mock_module("requests")
        mod.HTTPError = Exception
        mod.get = MagicMock()
        sys.modules["requests"] = mod


# Patch immediately at import time so subsequent imports in test files work.
_patch_external_imports()


def make_logger(name: str = "test") -> logging.Logger:
    """Return a real logger for injection into job classes under test."""
    return logging.getLogger(name)
