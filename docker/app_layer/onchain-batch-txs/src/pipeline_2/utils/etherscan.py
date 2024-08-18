import requests, logging
from requests.exceptions import InvalidSchema, ConnectionError

class EthercanAPI:

    def __init__(self, api_key, network):
        DICT_NETWORK = {'mainnet': 'api.etherscan.io','goerli': 'api-goerli.etherscan.io', 'polygon-main': 'polygonscan.com'}
        self.api_key = api_key
        network_url = DICT_NETWORK.get(network, None)
        self.url = f"https://{network_url}/api"


    def get_account_balance(self, address):
        base_uri_method = "module=account&action=balance"
        url_request = f"{self.url}?{base_uri_method}&address={address}&tag=latest&apikey={self.api_key}"
        response = self.make_request_to_etherscan(url_request)
        return response


    def get_block_by_timestamp(self, timestamp, closest='before'):
        base_uri_method = "module=block&action=getblocknobytime"
        url_request = f"{self.url}?{base_uri_method}&timestamp={timestamp}&closest={closest}&apikey={self.api_key}"
        response = self.make_request_to_etherscan(url_request)
        return response


    def get_contract_logs_by_block_interval(self, address, fromblock, toblock, page=1, offset=100):
        base_uri_method = "module=logs&action=getLogs"
        url_request = f"{self.url}?{base_uri_method}&address={address}&" + \
            f"fromBlock={fromblock}&toBlock={toblock}&page={page}&offset={offset}&apikey={self.api_key}"
        response = self.make_request_to_etherscan(url_request)
        return response
    

    def get_contract_transactions_by_block_interval(self, address, startblock, endblock, page=1, offset=100, sort='asc'):
        base_uri_method = "module=account&action=txlist"
        url_request = f"{self.url}?{base_uri_method}&address={address}" + \
            f"&startblock={startblock}&endblock={endblock}&page={page}" + \
            f"&offset={offset}&sort={sort}&apikey={self.api_key}"
        response = self.make_request_to_etherscan(url_request)
        return response


    def get_contract_abi(self, address):
        base_uri_method = "module=contract&action=getabi"
        url_request = f"{self.url}?{base_uri_method}&address={address}&apikey={self.api_key}"
        response = self.make_request_to_etherscan(url_request)
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
        return response


if __name__ == '__main__':
    pass