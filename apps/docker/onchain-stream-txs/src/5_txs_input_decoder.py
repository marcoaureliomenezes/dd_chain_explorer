"""
Job 5 — Transaction Input Decoder  (v2 — DynamoDB cache + multi-key Etherscan)
===============================================================================
Consumes ``mainnet.4.transactions.data``, decodes the ``input`` field for ALL
contract-call transactions and produces the result to
``mainnet.5.transactions.input_decoded``.

**Decode pipeline (in order):**

  1. DynamoDB ABI cache        → hit?  → full decode (method + typed params)
  2. Etherscan API (6 keys)    → ABI?  → cache + full decode
  3. 4byte.directory fallback  → sig?  → partial (method name only)
  4. Raw 4-byte selector       → last resort (never silently drops)

Negative cache: addresses whose ABI is NOT verified on Etherscan are marked in
DynamoDB with a 24 h TTL so the API is not hammered repeatedly.

See ``decode_inputs.md`` for the full design document.
"""

import json
import logging
import os
import uuid

from functools import lru_cache
from logging import Logger
from typing import Any, Dict, Optional

from eth_abi import decode as abi_decode
from web3 import Web3

from dm_chain_utils.dm_parameter_store import ParameterStoreClient
from dm_chain_utils.dm_kinesis import KinesisHandler
from dm_chain_utils.dm_firehose import FirehoseHandler
from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler

from utils_decode.abi_cache import ABICache
from utils_decode.etherscan_multi import MultiKeyEtherscanClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_value(val: Any) -> Any:
    """Recursively convert non-serializable types (bytes, HexBytes) to str."""
    if isinstance(val, (bytes, bytearray)):
        return val.hex()
    if isinstance(val, list):
        return [_serialize_value(x) for x in val]
    if isinstance(val, tuple):
        return [_serialize_value(x) for x in val]
    if isinstance(val, dict):
        return {str(k): _serialize_value(v) for k, v in val.items()}
    return val


def _serialize_params(params: dict) -> dict:
    return {k: _serialize_value(v) for k, v in params.items()}


def _parse_top_level_types(args_str: str) -> list:
    """Split ABI type list string at top-level commas only.

    Handles nested tuples, e.g.::

        'address,(uint256,bytes),uint256[]'
        → ['address', '(uint256,bytes)', 'uint256[]']
    """
    types: list = []
    depth = 0
    current: list = []
    for ch in args_str:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            token = "".join(current).strip()
            if token:
                types.append(token)
            current = []
        else:
            current.append(ch)
    token = "".join(current).strip()
    if token:
        types.append(token)
    return types


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TransactionInputDecoder:
    """
    Streaming job that decodes the ``input`` field of every non-deploy,
    non-ETH-transfer transaction and publishes the result to Kinesis.

    Uses:
      • ``ABICache``  (DynamoDB) — persistent, survives container restarts.
      • ``MultiKeyEtherscanClient`` — round-robin across 6 API keys.
    """

    def __init__(
        self,
        logger: Logger,
        abi_cache: ABICache,
        etherscan: MultiKeyEtherscanClient,
    ):
        self.logger    = logger
        self._cache    = abi_cache
        self._etherscan = etherscan
        # Web3 instance without a provider — only used for ABI codec
        self._w3 = Web3()

        # Running counters for progress logging
        self._cnt_cache_hit = 0
        self._cnt_api_call  = 0

    # ------------------------------------------------------------------
    # Source / Sink interface
    # ------------------------------------------------------------------

    def src_config(self, src_properties: Dict[str, Any]) -> "TransactionInputDecoder":
        self._kinesis_handler: KinesisHandler = src_properties["kinesis_handler"]
        self._stream_in = src_properties["stream_in"]
        self.logger.info(f"Source configured — Kinesis stream: {self._stream_in}")
        return self

    def sink_config(self, sink_properties: Dict[str, Any]) -> "TransactionInputDecoder":
        self._firehose_handler: FirehoseHandler = sink_properties["firehose_handler"]
        self._firehose_out = sink_properties["firehose_out"]
        self.logger.info(f"Sink configured — Firehose stream: {self._firehose_out}")
        return self

    def run(self) -> None:
        cache_stats = self._cache.stats()
        self.logger.info(
            f"Decoder started — DynamoDB cache: {cache_stats['cached_abis']} ABIs, "
            f"{cache_stats['unverified_addresses']} unverified addresses"
        )

        decoded_count  = 0
        skipped_count  = 0
        fallback_count = 0

        for record in self._kinesis_handler.consume_stream(self._stream_in):
            tx = json.loads(record["Data"])

            contract_address = tx.get("to", "")
            input_hex        = tx.get("input", "0x")

            # Normalize: bytes.hex() strips '0x'; Web3 decode needs it
            if not input_hex.startswith("0x"):
                input_hex = "0x" + input_hex

            # --- Skip contract deploys (to == "" or None) ---
            if not contract_address:
                skipped_count += 1
                continue

            # --- Skip plain ETH transfers (input == '0x' or too short) ---
            if not input_hex or input_hex in ("0x", "") or len(input_hex) < 10:
                skipped_count += 1
                continue

            result = self._decode_input(contract_address, input_hex)
            if result is None:
                skipped_count += 1
                continue

            # Drop truly unknown decodes — no useful data to publish
            if result["decode_type"] == "unknown":
                skipped_count += 1
                continue

            if result["decode_type"] == "partial":
                fallback_count += 1

            out_record = self._build_record(tx, contract_address, result)
            if out_record is None:
                skipped_count += 1
                continue

            try:
                self._firehose_handler.put_record(
                    self._firehose_out,
                    data=json.dumps(out_record, default=str),
                )
                decoded_count += 1
            except Exception as exc:
                self.logger.error(f"Produce error for {tx.get('hash')}: {exc}")

            if decoded_count % 500 == 0 and decoded_count > 0:
                self.logger.info(
                    f"Progress — decoded: {decoded_count}, "
                    f"fallback: {fallback_count}, skipped: {skipped_count}, "
                    f"cache_hit: {self._cnt_cache_hit}, api_call: {self._cnt_api_call}"
                )

    # ------------------------------------------------------------------
    # Decode logic
    # ------------------------------------------------------------------

    def _decode_input(self, contract_address: str, input_hex: str) -> dict:
        """
        Attempt to decode *input_hex* for *contract_address*.

        Pipeline:
          1. DynamoDB cache → full decode
          2. Etherscan API (multi-key) → store + full decode
          3. 4byte.directory → partial
          4. Raw selector → unknown
        """
        selector = input_hex[:10]  # '0x' + first 4 bytes
        addr = contract_address.lower()

        # ---- 1. DynamoDB cache ----
        abi = self._cache.get(addr)
        if abi:
            self._cnt_cache_hit += 1
            decoded = self._decode_with_abi(addr, abi, input_hex)
            if decoded:
                return decoded

        # ---- 2. Etherscan API (skip if negative-cached) ----
        if not self._cache.is_unverified(addr) and abi is None:
            self._cnt_api_call += 1
            abi = self._etherscan.fetch_contract_abi(addr)
            if abi:
                self._cache.put(addr, abi)
                decoded = self._decode_with_abi(addr, abi, input_hex)
                if decoded:
                    return decoded
            else:
                # Mark as unverified → won't hit Etherscan again for 24 h
                self._cache.mark_unverified(addr)

        # ---- 3. Fallback: 4byte.directory — try to decode params from sig ----
        sig = self._etherscan.get_4byte_signature(selector)
        if sig:
            self.logger.debug(f"[decode] 4byte fallback for {addr}: {sig}")
            return self._decode_with_sig(sig, input_hex)

        # ---- 4. Last resort: raw selector — unknown, will be dropped ----
        self.logger.debug(f"[decode] Unknown selector {selector} for {addr}")
        return {"method": selector, "parms": {}, "decode_type": "unknown"}

    @lru_cache(maxsize=4096)
    def _get_contract(self, address: str, abi_json: str):
        """Cache the web3 Contract object (keyed by address + serialized ABI)."""
        abi = json.loads(abi_json)
        checksum = Web3.to_checksum_address(address)
        return self._w3.eth.contract(address=checksum, abi=abi)

    def _decode_with_abi(
        self, address: str, abi: list, input_hex: str
    ) -> Optional[dict]:
        try:
            abi_json = json.dumps(abi, sort_keys=True)
            contract = self._get_contract(address.lower(), abi_json)
            func_obj, params = contract.decode_function_input(input_hex)
            # Extract just the function name (no type signature)
            raw = str(func_obj)  # e.g. "<Function transfer(address,uint256)>"
            if "<Function " in raw:
                method_name = raw.split("<Function ")[1].rstrip(">").split("(")[0]
            else:
                method_name = str(func_obj)
            clean_params = _serialize_params(params)
            return {
                "method": method_name,
                "parms":  clean_params,
                "decode_type": "full",
            }
        except Exception as exc:
            self.logger.debug(f"[decode] ABI decode failed for {address}: {exc}")
            return None

    def _decode_with_sig(self, sig: str, input_hex: str) -> dict:
        """
        Attempt full parameter decode using a 4byte.directory signature.

        Given ``sig = 'transfer(address,uint256)'``:
          1. Extract method name  → 'transfer'
          2. Parse param types    → ['address', 'uint256']
          3. Decode calldata with eth_abi.decode

        Falls back to decode_type='partial' (method name only) if param decode
        fails (bad calldata, complex tuple that can't be parsed, etc.).
        """
        paren = sig.index("(") if "(" in sig else len(sig)
        method_name = sig[:paren]
        args_str = sig[paren + 1: -1] if "(" in sig else ""

        if args_str:
            try:
                types = _parse_top_level_types(args_str)
                calldata = bytes.fromhex(input_hex[10:])   # skip 4-byte selector
                values = abi_decode(types, calldata)
                clean = {f"arg{i}": _serialize_value(v) for i, v in enumerate(values)}
                return {"method": method_name, "parms": clean, "decode_type": "full_4byte"}
            except Exception as exc:
                self.logger.debug(
                    f"[decode] 4byte param decode failed for sig '{sig}': {exc}"
                )

        # method name available but params could not be decoded
        return {"method": method_name, "parms": {}, "decode_type": "partial"}

    # ------------------------------------------------------------------
    # Record builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_record(
        tx: dict,
        contract_address: str,
        result: dict,
    ) -> Optional[dict]:
        """
        Build the output record.

        Only ``tx_hash`` is kept from the source transaction — ``from``,
        ``block_number`` and ``input`` are already on the source topic and
        can be joined back using ``tx_hash``.
        """
        try:
            return {
                "tx_hash":          tx["hash"],
                "contract_address": contract_address,
                "method":           result["method"],
                "parms":            json.dumps(result["parms"]),
                "decode_type":      result["decode_type"],
            }
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    APP_NAME             = "TRANSACTION_INPUT_DECODER"
    NETWORK              = os.getenv("NETWORK", "mainnet")
    CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP")
    KINESIS_STREAM_TRANSACTIONS = os.getenv("KINESIS_STREAM_TRANSACTIONS")
    FIREHOSE_STREAM_DECODED     = os.getenv("FIREHOSE_STREAM_DECODED")
    SSM_ETHERSCAN_PATH   = os.getenv("SSM_ETHERSCAN_PATH", "/etherscan-api-keys")
    UNVERIFIED_TTL       = int(os.getenv("UNVERIFIED_TTL", "86400"))  # 24 h

    PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s — %(levelname)s — %(message)s",
    )
    logger = logging.getLogger(APP_NAME)

    # CloudWatch logging handler — replaces KafkaLoggingHandler
    logger.addHandler(CloudWatchLoggingHandler(
        log_group=CLOUDWATCH_LOG_GROUP,
        log_stream=f"{APP_NAME.lower()}-{PROC_ID}",
    ))
    logger.info("CloudWatch logging handler configured.")

    kinesis_handler = KinesisHandler(logger)
    firehose_handler = FirehoseHandler(logger)
    logger.info("Kinesis (src) and Firehose (sink) handlers configured.")

    # ---- ABI cache (DynamoDB) ----
    abi_cache = ABICache(logger, unverified_ttl=UNVERIFIED_TTL)
    if abi_cache.ping():
        logger.info("ABICache connected (DynamoDB).")
    else:
        logger.error("ABICache — DynamoDB connection FAILED. Exiting.")
        raise SystemExit(1)

    # ---- Etherscan multi-key client ----
    ssm = ParameterStoreClient()
    etherscan_keys_map = ssm.get_parameters_by_path(SSM_ETHERSCAN_PATH)
    etherscan_keys = list(etherscan_keys_map.values())
    if not etherscan_keys:
        logger.error(
            f"No Etherscan API keys found under SSM path '{SSM_ETHERSCAN_PATH}'. "
            "Cannot proceed without at least one key."
        )
        raise SystemExit(1)
    logger.info(f"Loaded {len(etherscan_keys)} Etherscan API keys from SSM.")

    etherscan = MultiKeyEtherscanClient(
        logger,
        api_keys=etherscan_keys,
        network=NETWORK,
        api_key_names=list(etherscan_keys_map.keys()),
    )

    # ---- Run ----
    src_properties = {
        "kinesis_handler": kinesis_handler,
        "stream_in": KINESIS_STREAM_TRANSACTIONS,
    }
    sink_properties = {
        "firehose_handler": firehose_handler,
        "firehose_out": FIREHOSE_STREAM_DECODED,
    }

    _ = (
        TransactionInputDecoder(logger, abi_cache, etherscan)
            .src_config(src_properties)
            .sink_config(sink_properties)
            .run()
    )