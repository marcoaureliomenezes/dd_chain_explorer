"""
Etherscan API v2 client with disk-based ABI cache and 4byte.directory fallback.

Strategy for decoding ANY transaction input:
  1. Try Etherscan API → fetch verified contract ABI   → full decode (method + params)
  2. Fallback to 4byte.directory → lookup 4-byte selector  → method name only (params raw hex)
  3. If both fail → return None (skip message)

API v2 routes requests via `chainid` query parameter instead of subdomain.
  mainnet  → chainid=1
  goerli   → chainid=5
  sepolia  → chainid=11155111

Usage:
    from utils.dm_etherscan import EtherscanClient

    client = EtherscanClient(logger, api_key, network='mainnet')
    abi = client.get_contract_abi('0xAbcd...')          # None if unverified
    sig = client.get_4byte_signature('0x38ed1739')      # fallback method name
"""

import json
import logging
import os

import requests
from functools import lru_cache
from logging import Logger
from pathlib import Path
from typing import Optional


_ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"

_ETHERSCAN_CHAIN_IDS = {
    "mainnet": 1,
    "goerli":  5,
    "sepolia": 11155111,
}

_4BYTE_URL = "https://www.4byte.directory/api/v1/signatures/"

# Disk cache dir — survives across runs within the same container lifetime
_ABI_CACHE_DIR = Path(os.getenv("ABI_CACHE_DIR", "/tmp/abi_cache"))


class EtherscanClient:
    """Thin Etherscan API v2 wrapper with disk-backed ABI cache."""

    def __init__(self, logger: Logger, api_key: str, network: str = "mainnet"):
        self.logger   = logger
        self._api_key = api_key
        self._chain_id = _ETHERSCAN_CHAIN_IDS.get(network, 1)
        self._base_url = _ETHERSCAN_V2_BASE
        _ABI_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_contract_abi(self, address: str) -> Optional[list]:
        """
        Return the ABI list for *address*, or None if not verified.
        Results are cached to disk so Etherscan is only called once per address.
        """
        address = address.lower()
        cached = self._load_from_disk(address)
        if cached is not None:
            return cached

        abi = self._fetch_abi_from_etherscan(address)
        if abi is not None:
            self._save_to_disk(address, abi)
        return abi

    def get_4byte_signature(self, selector: str) -> Optional[str]:
        """
        Query 4byte.directory for a human-readable function signature
        matching *selector* (e.g. '0x38ed1739').
        Returns the first match, e.g. 'swapExactTokensForTokens(uint256,...)'
        """
        try:
            resp = requests.get(
                _4BYTE_URL,
                params={"hex_signature": selector},
                timeout=5,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                return results[0]["text_signature"]
        except Exception as exc:
            self.logger.debug(f"[4byte] lookup failed for {selector}: {exc}")
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_abi_from_etherscan(self, address: str) -> Optional[list]:
        params = {
            "chainid": self._chain_id,
            "module":  "contract",
            "action":  "getabi",
            "address": address,
            "apikey":  self._api_key,
        }
        try:
            resp = requests.get(self._base_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            self.logger.warning(f"[Etherscan] HTTP error for {address}: {exc}")
            return None

        if data.get("status") != "1":
            # "Contract source code not verified" → expected, not an error
            self.logger.debug(
                f"[Etherscan] ABI not available for {address}: {data.get('result')}"
            )
            return None

        try:
            abi = json.loads(data["result"])
            self.logger.debug(f"[Etherscan] ABI fetched for {address}")
            return abi
        except (json.JSONDecodeError, KeyError) as exc:
            self.logger.warning(f"[Etherscan] ABI parse error for {address}: {exc}")
            return None

    @lru_cache(maxsize=4096)
    def _load_from_disk(self, address: str) -> Optional[list]:
        path = _ABI_CACHE_DIR / f"{address}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return None

    def _save_to_disk(self, address: str, abi: list) -> None:
        path = _ABI_CACHE_DIR / f"{address}.json"
        try:
            path.write_text(json.dumps(abi))
        except Exception as exc:
            self.logger.debug(f"[ABI cache] write failed for {address}: {exc}")
