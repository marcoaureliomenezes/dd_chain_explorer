"""
utils_decode/etherscan_multi.py

Cliente Etherscan com rotação round-robin de múltiplas API keys.

Com 6 chaves no free tier (5 req/s por chave), o throughput teórico é ~30 req/s.
Inclui throttle per-key para respeitar o rate limit da Etherscan.

Uso:
    from utils_decode.etherscan_multi import MultiKeyEtherscanClient

    client = MultiKeyEtherscanClient(logger, api_keys=["k1", "k2", ...])
    abi    = client.fetch_contract_abi("0xAbCd...")    # round-robin + throttle
    sig    = client.get_4byte_signature("0x38ed1739")  # 4byte.directory (sem key)
"""

import json
import logging
import time
from typing import Optional

import requests


_ETHERSCAN_NETWORKS = {
    "mainnet": "api.etherscan.io",
    "goerli":  "api-goerli.etherscan.io",
    "sepolia": "api-sepolia.etherscan.io",
}

_4BYTE_URL = "https://www.4byte.directory/api/v1/signatures/"

# Intervalo mínimo entre requests com a mesma API key (5 req/s → 0.21 s de margem)
_MIN_INTERVAL_SECS = 0.21


class MultiKeyEtherscanClient:
    """Etherscan API client com round-robin de API keys e rate-limiting."""

    def __init__(
        self,
        logger: logging.Logger,
        api_keys: list[str],
        network: str = "mainnet",
    ):
        if not api_keys:
            raise ValueError("At least one Etherscan API key is required.")

        self.logger    = logger
        self._api_keys = list(api_keys)
        self._index    = 0
        host = _ETHERSCAN_NETWORKS.get(network, "api.etherscan.io")
        self._base_url = f"https://{host}/api"

        # Timestamp do último request por key (para throttle)
        self._last_ts: dict[str, float] = {}

        self.logger.info(
            f"[EtherscanMulti] Initialized with {len(self._api_keys)} API keys, "
            f"network={network}"
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def fetch_contract_abi(self, address: str) -> Optional[list]:
        """
        Busca a ABI verificada de *address* na Etherscan.

        Usa a próxima API key no round-robin e aplica throttle per-key.

        Returns
        -------
        list | None
            ABI como lista de dicts, ou None se não verificada / erro.
        """
        key = self._next_key()
        self._throttle(key)

        params = {
            "module":  "contract",
            "action":  "getabi",
            "address": address,
            "apikey":  key,
        }
        try:
            resp = requests.get(self._base_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            self.logger.warning(f"[EtherscanMulti] HTTP error for {address}: {exc}")
            return None

        if data.get("status") != "1":
            msg = data.get("result", "")
            # "Max rate limit reached" → log como warning; outros são debug
            if "rate limit" in msg.lower():
                self.logger.warning(f"[EtherscanMulti] Rate limited on key ...{key[-4:]}")
            else:
                self.logger.debug(
                    f"[EtherscanMulti] ABI not available for {address}: {msg}"
                )
            return None

        try:
            abi = json.loads(data["result"])
            self.logger.debug(f"[EtherscanMulti] ABI fetched for {address}")
            return abi
        except (json.JSONDecodeError, KeyError) as exc:
            self.logger.warning(
                f"[EtherscanMulti] ABI parse error for {address}: {exc}"
            )
            return None

    @staticmethod
    def get_4byte_signature(selector: str) -> Optional[str]:
        """
        Consulta 4byte.directory pelo selector hex (ex: '0x38ed1739').

        Returns
        -------
        str | None
            Assinatura legível (ex: 'swapExactTokensForTokens(uint256,...)'),
            ou None se não encontrada.
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
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _next_key(self) -> str:
        """Retorna a próxima API key em round-robin."""
        key = self._api_keys[self._index % len(self._api_keys)]
        self._index += 1
        return key

    def _throttle(self, key: str) -> None:
        """
        Pausa o tempo necessário para respeitar o rate limit da key.

        Garante que o intervalo entre requests com a mesma key seja ≥ _MIN_INTERVAL_SECS.
        """
        now  = time.time()
        last = self._last_ts.get(key, 0.0)
        wait = _MIN_INTERVAL_SECS - (now - last)
        if wait > 0:
            time.sleep(wait)
        self._last_ts[key] = time.time()
