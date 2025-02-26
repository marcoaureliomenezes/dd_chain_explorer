import requests, logging
from typing import List
from requests.exceptions import InvalidSchema, ConnectionError

class EthercanAPI:

    def __init__(self, logger, akv_client, api_key_name, network):
        self.logger = logger
        self.api_key_name = api_key_name
        self.api_key_secret = akv_client.get_secret(self.api_key_name).value
        self.akv_client = akv_client
        self.url = f"https://{self.get_network_url(network)}/api"
        self.setup_pagination()


    def setup_pagination(self, page=1, offset=1000, sort='asc'):
        self.page = page
        self.offset = offset
        self.sort = sort

    def get_network_url(self, network):
        dict_networks = {
            'mainnet': 'api.etherscan.io',
            'goerli': 'api-goerli.etherscan.io',
            'polygon-main': 'polygonscan.com'
        }
        return dict_networks.get(network, None)




    def get_accounts_balance(self, addresses: List):
        addresses = ','.join(addresses)
        base_uri = "module=account&action=balance"
        url = f"{self.url}?{base_uri}&address={addresses}&tag=latest&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


    def get_block_by_timestamp(self, timestamp, closest='before'):
        base_uri = "module=block&action=getblocknobytime"
        url = f"{self.url}?{base_uri}&timestamp={timestamp}&closest={closest}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


    def get_contract_logs_by_block_interval(self, address, fromblock, toblock):
        base_uri = "module=logs&action=getLogs"
        url = f"{self.url}?{base_uri}&address={address}&" + \
            f"fromBlock={fromblock}&toBlock={toblock}&page={self.page}&" + \
            f"offset={self.offset}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response
    

    def get_contract_txs_by_block_interval(self, address, startblock, endblock):
        base_uri = "module=account&action=txlist"
        url = f"{self.url}?{base_uri}&address={address}" + \
            f"&startblock={startblock}&endblock={endblock}&page={self.page}" + \
            f"&offset={self.offset}&sort={self.sort}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response

    def get_internal_txs_by_block_interval(self, address, startblock, endblock):
        base_uri = "module=account&action=txlistinternal"
        url = f"{self.url}?{base_uri}&address={address}" + \
            f"&startblock={startblock}&endblock={endblock}&page={self.page}" + \
            f"&offset={self.offset}&sort={self.sort}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response

    def get_contract_abi(self, address):
        base_uri = "module=contract&action=getabi"
        url = f"{self.url}?{base_uri}&address={address}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


    def get_total_nodes_count(self):
        req = "https://api.etherscan.io/api?module=stats&action=nodecount&apikey=YourApiKeyToken"

    def get_latest_eth_price(self):
        req = "https://api.etherscan.io/api?module=stats&action=ethprice&apikey=YourApiKeyToken"


    def get_eth_supply(self):
        req = "https://api.etherscan.io/api?module=stats&action=ethsupply2&apikey=YourApiKeyToken"

    def get_eth2_supply(self):
        req = "https://api.etherscan.io/api?module=stats&action=ethsupply2&apikey=YourApiKeyToken"

    def get_gas_estimate(self):
        req = "https://api.etherscan.io/api?module=gastracker&action=gasestimate&gasprice=2000000000 &apikey=YourApiKeyToken"


    # TriggerDragRun: For when the trigger event comes from another DAG in the same environment. Pass trigger_dag_id and wait_for_completion=True
    # Sensors: For when the trigger event comes from an external source. Pass external_trigger=True and wait_for_completion=True
    # Deferrable Operators
    # Airflow API.
    def make_request_to_etherscan(self, request_url):
        try:
            response = requests.get(request_url)
            response = response.json()
        except AttributeError:
            print('Problema de atributo...')
            response = None
        except ConnectionError: 
            print('Problema de conexão...')
            response = None
        else:
            self.logger.info(f"API_KEY:{self.api_key_name};STATUS_CODE:{response['status']}")
        return response


if __name__ == '__main__':
    pass