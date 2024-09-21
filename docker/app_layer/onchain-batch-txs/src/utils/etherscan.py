import requests, logging
from requests.exceptions import InvalidSchema, ConnectionError

class EthercanAPI:

    def __init__(self, logger, akv_client, api_key_name, network):
        self.logger = logger
        self.api_key_name = api_key_name
        self.api_key_secret = akv_client.get_secret(self.api_key_name).value
        self.akv_client = akv_client
        self.url = f"https://{self.get_network_url(network)}/api"

    def get_network_url(self, network):
        dict_networks = {
            'mainnet': 'api.etherscan.io',
            'goerli': 'api-goerli.etherscan.io',
            'polygon-main': 'polygonscan.com'
        }
        return dict_networks.get(network, None)


    def get_account_balance(self, address):
        base_uri = "module=account&action=balance"
        url = f"{self.url}?{base_uri}&address={address}&tag=latest&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


    def get_block_by_timestamp(self, timestamp, closest='before'):
        base_uri = "module=block&action=getblocknobytime"
        url = f"{self.url}?{base_uri}&timestamp={timestamp}&closest={closest}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


    def get_contract_logs_by_block_interval(self, address, fromblock, toblock, page=1, offset=100):
        base_uri = "module=logs&action=getLogs"
        url = f"{self.url}?{base_uri}&address={address}&" + \
            f"fromBlock={fromblock}&toBlock={toblock}&page={page}&offset={offset}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response
    

    def get_contract_tx_by_block_interval(self, address, startblock, endblock, page=1, offset=100, sort='asc'):
        base_uri = "module=account&action=txlist"
        url = f"{self.url}?{base_uri}&address={address}" + \
            f"&startblock={startblock}&endblock={endblock}&page={page}" + \
            f"&offset={offset}&sort={sort}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


    def get_contract_abi(self, address):
        base_uri = "module=contract&action=getabi"
        url = f"{self.url}?{base_uri}&address={address}&apikey={self.api_key_secret}"
        response = self.make_request_to_etherscan(url)
        return response


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