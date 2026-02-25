class PopularContractsCacheValidator:

    def __init__(self):
        self.pop = None
        self.cache = None

    def run(self, **kwargs):
        print("VALIDATING CACHE HEY OK!")
        return "GET_POPULAR_CONTRACTS_AND_CACHE_IT" if False else "BY_PASS"
