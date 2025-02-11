from web3 import Web3
from web3.exceptions import TransactionNotFound
from azure.keyvault.secrets import SecretClient
from logging import Logger
from requests import HTTPError
from typing import Dict, Optional

class Web3Handler:

  def __init__(self, logger: Logger, akv_client: SecretClient, network: str):
    self.akv_client = akv_client
    self.logger = logger
    self.network = network


  def get_node_connection(self, api_key_name: str, vendor: str) -> Web3:
    self.api_key_name = api_key_name
    api_key = self.akv_client.get_secret(api_key_name).value
    self.logger.info(f"KEY_VAULT_REQUEST: {api_key_name}")
    dict_vendors = { 
    'alchemy': f"https://eth-{self.network}.g.alchemy.com/v2/{api_key}",
    'infura': f"https://{self.network}.infura.io/v3/{api_key}"}
    vendor_url = dict_vendors.get(vendor)
    self.web3 = Web3(Web3.HTTPProvider(vendor_url))
    self.logger.info(f"API_KEY set;{api_key_name}")
    return self
    

  def extract_block_data(self, block_num='latest') -> Optional[Dict]:
    try: block_data = self.web3.eth.get_block(block_num)
    except HTTPError as err:
      self.logger.error(f"API_request;{self.api_key_name};Error:{str(err)}") ; return
    self.logger.info(f"API_request;{self.api_key_name}")
    return block_data
  

  def parse_block_data(self, raw_data: Dict) -> Dict:
    return {
      "number": raw_data['number'],
      "timestamp": raw_data['timestamp'],
      "hash": bytes.hex(raw_data['hash']),
      "parentHash": bytes.hex(raw_data['parentHash']),
      "difficulty": raw_data['difficulty'],
      "totalDifficulty": str(raw_data.get('totalDifficulty')),
      "nonce": bytes.hex(raw_data['nonce']),
      "size": raw_data['size'],
      "miner": raw_data['miner'],
      "baseFeePerGas": raw_data['baseFeePerGas'],
      "gasLimit": raw_data['gasLimit'],
      "gasUsed": raw_data['gasUsed'],
      "logsBloom": bytes.hex(raw_data['logsBloom']),
      "extraData": bytes.hex(raw_data['extraData']),
      "transactionsRoot": bytes.hex(raw_data['transactionsRoot']),
      "stateRoot": bytes.hex(raw_data['stateRoot']),
      "transactions": [bytes.hex(i) for i in raw_data['transactions']],
      "withdrawals": [dict(i) for i in raw_data['withdrawals']]}
  

  def extract_tx_data(self, tx_id: str) -> Dict:
    try: tx_data = self.web3.eth.get_transaction(tx_id)
    except TransactionNotFound:
      self.logger.error(f"Transaction not found: {tx_id}") ; return
    self.logger.info(f"API_request;{self.actual_api_key}")
    return tx_data