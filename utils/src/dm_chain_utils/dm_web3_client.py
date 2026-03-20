from web3 import Web3
from web3.exceptions import TransactionNotFound
from logging import Logger
from requests import HTTPError
from typing import Dict, Optional
from hexbytes import HexBytes
import os

from dm_chain_utils.dm_parameter_store import ParameterStoreClient


def _convert_hexbytes_to_str(data):
    """Recursively convert HexBytes to hex strings in a dict/list structure."""
    if isinstance(data, dict):
        return {k: _convert_hexbytes_to_str(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_hexbytes_to_str(i) for i in data]
    if isinstance(data, HexBytes):
        return bytes.hex(data)
    return data


class Web3Handler:

    def __init__(self, logger: Logger, network: str):
        self.logger = logger
        self.network = network
        self._ssm = ParameterStoreClient()

    def get_node_connection(self, api_key_name: str, vendor: str) -> "Web3Handler":
        self.api_key_name = api_key_name
        api_key = self._ssm.get_parameter(api_key_name)
        self.logger.info(f"SSM_PARAMETERS_STORE_REQUEST: {api_key_name}")
        dict_vendors = {
            'alchemy': f"https://eth-{self.network}.g.alchemy.com/v2/{api_key}",
            'infura':  f"https://{self.network}.infura.io/v3/{api_key}",
        }
        vendor_url = dict_vendors.get(vendor)
        self.web3 = Web3(Web3.HTTPProvider(vendor_url))
        self.logger.info(f"API_KEY set;{api_key_name}")
        return self

    def extract_block_data(self, block_num='latest') -> Optional[Dict]:
        try:
            block_data = self.web3.eth.get_block(block_num)
        except HTTPError as err:
            self.logger.error(f"API_request;{self.api_key_name};Error:{str(err)}")
            return None
        self.logger.info(f"API_request;{self.api_key_name}")
        return block_data

    def parse_block_data(self, raw_data: Dict) -> Dict:
        return {
            "number":           raw_data['number'],
            "timestamp":        raw_data['timestamp'],
            "hash":             bytes.hex(raw_data['hash']),
            "parentHash":       bytes.hex(raw_data['parentHash']),
            "difficulty":       raw_data['difficulty'],
            "totalDifficulty":  str(raw_data.get('totalDifficulty')),
            "nonce":            bytes.hex(raw_data['nonce']),
            "size":             raw_data['size'],
            "miner":            raw_data['miner'],
            "baseFeePerGas":    raw_data['baseFeePerGas'],
            "gasLimit":         raw_data['gasLimit'],
            "gasUsed":          raw_data['gasUsed'],
            "logsBloom":        bytes.hex(raw_data['logsBloom']),
            "extraData":        bytes.hex(raw_data['extraData']),
            "transactionsRoot": bytes.hex(raw_data['transactionsRoot']),
            "stateRoot":        bytes.hex(raw_data['stateRoot']),
            "transactions":     [bytes.hex(i) for i in raw_data['transactions']],
            "withdrawals":      [dict(i) for i in raw_data['withdrawals']],
        }

    def extract_tx_data(self, tx_id: str) -> Optional[Dict]:
        try:
            tx_data = self.web3.eth.get_transaction(tx_id)
        except TransactionNotFound:
            self.logger.error(f"Transaction not found: {tx_id}")
            return None
        except HTTPError as err:
            self.logger.error(f"API_request;{self.api_key_name};HTTPError:{str(err)}")
            raise  # propagate so callers can rotate keys on 429 rate limit
        self.logger.info(f"API_request;{self.api_key_name}")
        return tx_data

    def parse_transaction_data(self, tx_data) -> Dict:
        parsed = _convert_hexbytes_to_str(dict(tx_data))
        return {
            "blockHash":             parsed["blockHash"],
            "blockNumber":           parsed["blockNumber"],
            "hash":                  parsed["hash"],
            "transactionIndex":      parsed["transactionIndex"],
            "from":                  parsed["from"],
            "to":                    parsed["to"] if parsed["to"] else "",
            "value":                 str(parsed["value"]),
            "input":                 parsed["input"],
            "gas":                   parsed["gas"],
            "gasPrice":              parsed["gasPrice"],
            "maxFeePerGas":          parsed.get("maxFeePerGas"),
            "maxPriorityFeePerGas":  parsed.get("maxPriorityFeePerGas"),
            "nonce":                 parsed["nonce"],
            "v":                     parsed["v"],
            "r":                     parsed["r"],
            "s":                     parsed["s"],
            "type":                  parsed["type"],
            "accessList":            parsed.get("accessList", []),
        }
