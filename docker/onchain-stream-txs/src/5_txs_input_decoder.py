"""
Job 5 — Transaction Input Decoder  (v2 — Redis cache + multi-key Etherscan)
============================================================================
Consumes ``mainnet.4.transactions.data``, decodes the ``input`` field for ALL
contract-call transactions and produces the result to
``mainnet.5.transactions.input_decoded``.

**Decode pipeline (in order):**

  1. Redis ABI cache (DB 6)    → hit?  → full decode (method + typed params)
  2. Etherscan API (6 keys)    → ABI?  → cache + full decode
  3. 4byte.directory fallback  → sig?  → partial (method name only)
  4. Raw 4-byte selector       → last resort (never silently drops)

Negative cache: addresses whose ABI is NOT verified on Etherscan are marked in
Redis with a 24 h TTL so the API is not hammered repeatedly.

See ``decode_inputs.md`` for the full design document.
"""

import argparse
import json
import logging
import os
import uuid

from configparser import ConfigParser
from functools import lru_cache
from logging import Logger
from typing import Any, Dict, Optional

from web3 import Web3

from utils.dm_parameter_store import ParameterStoreClient
from utils.dm_schema_reg_client import get_schema
from utils.dm_kafka_client import KafkaHandler
from utils.dm_logger import KafkaLoggingHandler

from utils_decode.abi_cache import ABICache
from utils_decode.etherscan_multi import MultiKeyEtherscanClient

from chain_extractor import ChainExtractor


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


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TransactionInputDecoder(ChainExtractor):
    """
    Streaming job that decodes the ``input`` field of every non-deploy,
    non-ETH-transfer transaction and publishes the result to Kafka.

    Uses:
      • ``ABICache``  (Redis DB 6) — persistent, survives container restarts.
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
    # ChainExtractor interface
    # ------------------------------------------------------------------

    def src_config(self, src_properties: Dict[str, Any]) -> "TransactionInputDecoder":
        self._consumer = src_properties["consumer"]
        self._topic_in = src_properties["topic_in"]
        self._consumer.subscribe([self._topic_in])
        self.logger.info(f"Source configured — topic: {self._topic_in}")
        return self

    def sink_config(self, sink_properties: Dict[str, Any]) -> "TransactionInputDecoder":
        self._producer  = sink_properties["producer"]
        self._topic_out = sink_properties["topic_out"]
        self.logger.info(f"Sink configured — topic: {self._topic_out}")
        return self

    def run(self, callback: Any) -> None:
        cache_stats = self._cache.stats()
        self.logger.info(
            f"Decoder started — Redis cache: {cache_stats['cached_abis']} ABIs, "
            f"{cache_stats['unverified_addresses']} unverified addresses"
        )

        decoded_count  = 0
        skipped_count  = 0
        fallback_count = 0

        for msg in self.consuming_topic(self._consumer):
            tx = msg["value"]

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

            if result["decode_type"] in ("partial", "unknown"):
                fallback_count += 1

            record = self._build_record(tx, contract_address, input_hex, result)
            if record is None:
                skipped_count += 1
                continue

            try:
                self._producer.produce(
                    self._topic_out,
                    key=tx["hash"],
                    value=record,
                    on_delivery=callback,
                )
                self._producer.flush()
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
          1. Redis cache → full decode
          2. Etherscan API (multi-key) → store + full decode
          3. 4byte.directory → partial
          4. Raw selector → unknown
        """
        selector = input_hex[:10]  # '0x' + first 4 bytes
        addr = contract_address.lower()

        # ---- 1. Redis cache ----
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

        # ---- 3. Fallback: 4byte.directory ----
        sig = self._etherscan.get_4byte_signature(selector)
        if sig:
            self.logger.debug(f"[decode] 4byte fallback for {addr}: {sig}")
            return {"method": sig, "parms": {}, "decode_type": "partial"}

        # ---- 4. Last resort: raw selector ----
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
            method_name = str(func_obj).split("<Function ")[1].rstrip(">")
            clean_params = _serialize_params(params)
            return {
                "method": method_name,
                "parms":  clean_params,
                "decode_type": "full",
            }
        except Exception as exc:
            self.logger.debug(f"[decode] ABI decode failed for {address}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Record builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_record(
        tx: dict,
        contract_address: str,
        input_hex: str,
        result: dict,
    ) -> Optional[dict]:
        try:
            parms_with_meta = dict(result["parms"])
            parms_with_meta["_decode_type"] = result["decode_type"]
            return {
                "tx_hash":          tx["hash"],
                "block_number":     tx["blockNumber"],
                "from":             tx["from"],
                "contract_address": contract_address,
                "input":            input_hex,
                "method":           result["method"],
                "parms":            json.dumps(parms_with_meta),
            }
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    APP_NAME            = "TRANSACTION_INPUT_DECODER"
    NETWORK             = os.getenv("NETWORK", "mainnet")
    KAFKA_BROKERS       = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
    SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
    TOPIC_LOGS          = os.getenv("TOPIC_LOGS")
    TOPIC_TXS_DATA      = os.getenv("TOPIC_TXS_DATA",    "mainnet.4.transactions.data")
    TOPIC_TXS_DECODED   = os.getenv("TOPIC_TXS_DECODED", "mainnet.5.transactions.input_decoded")
    CONSUMER_GROUP      = os.getenv("CONSUMER_GROUP",     "cg_txs_input_decoder")
    SSM_ETHERSCAN_PATH  = os.getenv("SSM_ETHERSCAN_PATH", "/etherscan-api-keys")
    UNVERIFIED_TTL      = int(os.getenv("UNVERIFIED_TTL", "86400"))  # 24 h

    PROC_ID = f"job-{str(uuid.uuid4())[:8]}"

    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("config_producer", type=argparse.FileType("r"), help="Config Producers")
    parser.add_argument("config_consumer", type=argparse.FileType("r"), help="Config Consumers")
    args   = parser.parse_args()
    config = ConfigParser()
    config.read_file(args.config_producer)
    config.read_file(args.config_consumer)

    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s — %(levelname)s — %(message)s",
    )
    logger = logging.getLogger(APP_NAME)

    PRODUCER_CONF = {"client.id": PROC_ID, **KAFKA_BROKERS, **config["producer.general.config"]}
    CONSUMER_CONF = {
        "client.id": PROC_ID,
        **KAFKA_BROKERS,
        **config["consumer.general.config"],
        "group.id": CONSUMER_GROUP,
    }

    handler_kafka = KafkaHandler(logger, sc_url=SCHEMA_REGISTRY_URL)

    # ---- Schemas ----
    LOGS_SCHEMA_PATH    = "schemas/0_application_logs_avro.json"
    TXS_SCHEMA_PATH     = "schemas/4_transactions_schema_avro.json"
    DECODED_SCHEMA_PATH = "schemas/txs_contract_call_decoded.json"

    schema_app_logs = get_schema(schema_name="application-logs-schema",  schema_path=LOGS_SCHEMA_PATH)
    schema_txs      = get_schema(schema_name="transactions-schema",      schema_path=TXS_SCHEMA_PATH)
    schema_decoded  = get_schema(schema_name="input-transaction-schema", schema_path=DECODED_SCHEMA_PATH)

    # ---- Kafka logging handler ----
    producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
    logger.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
    logger.info("Kafka logging handler configured.")

    # ---- Kafka consumer / producer ----
    consumer_txs     = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_txs)
    producer_decoded = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_decoded)
    logger.info("AVRO consumer/producer configured.")

    # ---- ABI cache (Redis DB 6) ----
    abi_cache = ABICache(logger, redis_db=6, unverified_ttl=UNVERIFIED_TTL)
    if abi_cache.ping():
        logger.info("ABICache connected (Redis DB 6).")
    else:
        logger.error("ABICache — Redis connection FAILED. Exiting.")
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

    etherscan = MultiKeyEtherscanClient(logger, api_keys=etherscan_keys, network=NETWORK)

    # ---- Run ----
    src_properties = {
        "consumer": consumer_txs,
        "topic_in": TOPIC_TXS_DATA,
    }
    sink_properties = {
        "producer":  producer_decoded,
        "topic_out": TOPIC_TXS_DECODED,
    }

    _ = (
        TransactionInputDecoder(logger, abi_cache, etherscan)
            .src_config(src_properties)
            .sink_config(sink_properties)
            .run(callback=handler_kafka.message_handler)
    )