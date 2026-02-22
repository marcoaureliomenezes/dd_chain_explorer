"""
Job 5 — Transaction Input Decoder
==================================
Consumes `mainnet.4.transactions.data`, decodes the `input` field for ALL
contract-call transactions (skip deploys and plain ETH transfers), and
produces the decoded result to `mainnet.5.transactions.input_decoded`.

Decode strategy (in order):
  1. Etherscan ABI lookup → full decode (method name + typed params)
  2. 4byte.directory fallback → method name only (params left empty)
  3. Raw 4-byte selector as method → last resort (never silently drops)

ABI results are disk-cached in /tmp/abi_cache/ so Etherscan is hit only
once per contract address across the job lifetime.
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
from utils.etherscan_utils import EtherscanClient
from utils.schema_registry_utils import get_schema
from utils.kafka_utils import KafkaHandler
from utils.logger_utils import KafkaLoggingHandler

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
    Streaming job that decodes the `input` field of every non-deploy,
    non-ETH-transfer transaction and writes the result to Kafka.
    """

    def __init__(self, logger: Logger, etherscan: EtherscanClient):
        self.logger     = logger
        self.etherscan  = etherscan
        # Web3 instance without a provider — only used for ABI codec (no RPC calls)
        self._w3 = Web3()

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
        self.logger.info("Transaction Input Decoder started.")
        decoded_count  = 0
        skipped_count  = 0
        fallback_count = 0

        for msg in self.consuming_topic(self._consumer):
            tx = msg["value"]

            contract_address = tx.get("to", "")
            input_hex        = tx.get("input", "0x")

            # Normalize: dm_utils.convert_hexbytes_to_str uses bytes.hex() which
            # strips the '0x' prefix. Web3.py decode_function_input and the 4-byte
            # selector extraction both require the '0x' prefix to work correctly.
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

            if decoded_count % 100 == 0 and decoded_count > 0:
                self.logger.info(
                    f"Progress — decoded: {decoded_count}, "
                    f"fallback: {fallback_count}, skipped: {skipped_count}"
                )

    # ------------------------------------------------------------------
    # Decode logic
    # ------------------------------------------------------------------

    def _decode_input(self, contract_address: str, input_hex: str) -> dict:
        """
        Attempt to decode *input_hex* for *contract_address*.

        Returns a dict with keys: method, parms, decode_type.
        Never returns None — always produces at least the raw selector.
        """
        selector = input_hex[:10]  # '0x' + first 4 bytes

        # ---- 1. Try Etherscan ABI (full decode) ----
        abi = self.etherscan.get_contract_abi(contract_address)
        if abi:
            decoded = self._decode_with_abi(contract_address, abi, input_hex)
            if decoded:
                return decoded

        # ---- 2. Fallback: 4byte.directory (method name only) ----
        sig = self.etherscan.get_4byte_signature(selector)
        if sig:
            self.logger.debug(
                f"[decode] 4byte fallback for {contract_address}: {sig}"
            )
            return {"method": sig, "parms": {}, "decode_type": "partial"}

        # ---- 3. Last resort: raw selector ----
        self.logger.debug(
            f"[decode] Unknown selector {selector} for {contract_address}"
        )
        return {"method": selector, "parms": {}, "decode_type": "unknown"}

    @lru_cache(maxsize=2048)
    def _get_contract(self, address: str, abi_json: str):
        """Cache the web3 contract object (keyed by address + serialized ABI)."""
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
            # e.g. '<Function swapExactTokensForTokens(uint256,uint256,...)>'
            method_name = str(func_obj).split("<Function ")[1].rstrip(">")
            clean_params = _serialize_params(params)
            return {
                "method": method_name,
                "parms":  clean_params,
                "decode_type": "full",
            }
        except Exception as exc:
            self.logger.debug(
                f"[decode] ABI decode failed for {address}: {exc}"
            )
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

    APP_NAME          = "TRANSACTION_INPUT_DECODER"
    NETWORK           = os.getenv("NETWORK", "mainnet")
    KAFKA_BROKERS     = {"bootstrap.servers": os.getenv("KAFKA_BROKERS")}
    SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
    TOPIC_LOGS           = os.getenv("TOPIC_LOGS")
    TOPIC_TXS_DATA       = os.getenv("TOPIC_TXS_DATA",       "mainnet.4.transactions.data")
    TOPIC_TXS_DECODED    = os.getenv("TOPIC_TXS_DECODED",    "mainnet.5.transactions.input_decoded")
    CONSUMER_GROUP       = os.getenv("CONSUMER_GROUP",       "cg_txs_input_decoder")
    SSM_ETHERSCAN_KEY    = os.getenv("SSM_ETHERSCAN_KEY")    # SSM param name for Etherscan API key

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

    # Schemas
    LOGS_SCHEMA_PATH    = "schemas/0_application_logs_avro.json"
    TXS_SCHEMA_PATH     = "schemas/4_transactions_schema_avro.json"
    DECODED_SCHEMA_PATH = "schemas/txs_contract_call_decoded.json"

    schema_app_logs = get_schema(schema_name="application-logs-schema",  schema_path=LOGS_SCHEMA_PATH)
    schema_txs      = get_schema(schema_name="transactions-schema",       schema_path=TXS_SCHEMA_PATH)
    schema_decoded  = get_schema(schema_name="input-transaction-schema",  schema_path=DECODED_SCHEMA_PATH)

    # Kafka logging handler
    producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
    logger.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
    logger.info("Kafka logging handler configured.")

    # Consumers / Producers
    consumer_txs     = handler_kafka.create_avro_consumer(CONSUMER_CONF, schema_txs)
    producer_decoded = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_decoded)
    logger.info("AVRO consumer/producer configured.")

    # Etherscan client — API key from SSM
    ssm = ParameterStoreClient()
    etherscan_api_key = ssm.get_parameter(SSM_ETHERSCAN_KEY) if SSM_ETHERSCAN_KEY else ""
    if not etherscan_api_key:
        logger.warning(
            "No Etherscan API key found — ABI lookups will be rate-limited. "
            "Set SSM_ETHERSCAN_KEY env var."
        )
    etherscan = EtherscanClient(logger, etherscan_api_key, network=NETWORK)
    logger.info("EtherscanClient configured.")

    src_properties = {
        "consumer": consumer_txs,
        "topic_in": TOPIC_TXS_DATA,
    }
    sink_properties = {
        "producer":  producer_decoded,
        "topic_out": TOPIC_TXS_DECODED,
    }

    _ = (
        TransactionInputDecoder(logger, etherscan)
            .src_config(src_properties)
            .sink_config(sink_properties)
            .run(callback=handler_kafka.message_handler)
    )