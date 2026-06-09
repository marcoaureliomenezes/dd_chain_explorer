"""
Unit tests for MultiKeyEtherscanClient (utils_decode/etherscan_multi.py).

Covers:
  - F-02 (CWE-918 SSRF): invalid network names must be rejected with ValueError
    before any URL is constructed.
  - Valid network names must be accepted and produce the correct base URL.
  - Round-robin key rotation.
"""
import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Load etherscan_multi directly from source so we exercise the real class,
# NOT the conftest stub that replaces utils_decode.etherscan_multi.
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).parent.parent.parent / "src" / "utils_decode"
_MODULE_FILE = _SRC_DIR / "etherscan_multi.py"


def _load_module():
    # Ensure requests is stubbed before loading (conftest may have done this already)
    if "requests" not in sys.modules:
        import types
        mod = types.ModuleType("requests")
        mod.get = MagicMock()
        mod.HTTPError = Exception
        sys.modules["requests"] = mod
    spec = importlib.util.spec_from_file_location("etherscan_multi_real", _MODULE_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
MultiKeyEtherscanClient = _mod.MultiKeyEtherscanClient
_ETHERSCAN_NETWORKS = _mod._ETHERSCAN_NETWORKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger() -> logging.Logger:
    return logging.getLogger("test.etherscan_multi")


# ---------------------------------------------------------------------------
# F-02 — SSRF allowlist validation
# ---------------------------------------------------------------------------

class TestNetworkAllowlist:
    """F-02 (CWE-918): NETWORK env var must be validated against an explicit allowlist."""

    def test_valid_mainnet_accepted(self):
        client = MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network="mainnet")
        assert "api.etherscan.io" in client._base_url

    def test_valid_sepolia_accepted(self):
        client = MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network="sepolia")
        assert "api-sepolia.etherscan.io" in client._base_url

    def test_valid_goerli_accepted(self):
        client = MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network="goerli")
        assert "api-goerli.etherscan.io" in client._base_url

    def test_invalid_network_raises_value_error(self):
        """An unknown network must raise ValueError before URL construction."""
        with pytest.raises(ValueError, match="Invalid Etherscan network"):
            MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network="notanet")

    def test_empty_network_raises_value_error(self):
        """An empty string must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Etherscan network"):
            MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network="")

    def test_attacker_controlled_network_raises_value_error(self):
        """Attacker-supplied value must be rejected, preventing SSRF URL construction."""
        attacker_input = "evil.com/api?x="
        with pytest.raises(ValueError, match="Invalid Etherscan network"):
            MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network=attacker_input)

    def test_no_fallback_to_default_for_unknown_network(self):
        """Previously the code silently fell back to api.etherscan.io for unknown networks.
        After the fix, any unknown input must raise instead of silently using a default."""
        with pytest.raises(ValueError):
            MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network="unknown_net")

    def test_all_allowed_networks_accepted(self):
        """Every network in the allowlist must be accepted without raising."""
        for network in _ETHERSCAN_NETWORKS:
            client = MultiKeyEtherscanClient(_make_logger(), api_keys=["key1"], network=network)
            assert client._base_url.startswith("https://")


class TestConstructorGuards:
    """Constructor-level guard tests."""

    def test_no_api_keys_raises(self):
        with pytest.raises(ValueError, match="At least one Etherscan API key"):
            MultiKeyEtherscanClient(_make_logger(), api_keys=[], network="mainnet")

    def test_single_key_accepted(self):
        client = MultiKeyEtherscanClient(_make_logger(), api_keys=["mykey"], network="mainnet")
        assert client._api_keys == ["mykey"]


class TestRoundRobin:
    """Round-robin key rotation."""

    def test_next_key_cycles(self):
        keys = ["k1", "k2", "k3"]
        client = MultiKeyEtherscanClient(_make_logger(), api_keys=keys, network="mainnet")
        selected = [client._next_key() for _ in range(6)]
        assert selected == ["k1", "k2", "k3", "k1", "k2", "k3"]
