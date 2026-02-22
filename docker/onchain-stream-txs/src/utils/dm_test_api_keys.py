"""
dm_test_api_keys.py
-------------------
Busca todas as API Keys do AWS SSM Parameter Store e testa se estão funcionando.

Vendors suportados
  - infura    → Web3 HTTPProvider  https://{network}.infura.io/v3/{key}
  - alchemy   → Web3 HTTPProvider  https://eth-{network}.g.alchemy.com/v2/{key}
  - etherscan → Etherscan REST API https://api.etherscan.io/api?module=stats&action=ethsupply&apikey={key}

Uso rápido:
    python -m utils.dm_test_api_keys                  # mainnet, 5 reqs por chave
    python -m utils.dm_test_api_keys --num-reqs 20    # 20 reqs por chave
    python -m utils.dm_test_api_keys --network goerli

Uso como container (sem credenciais locais — assume IAM role/ECS task role):
    docker run --rm \\
      -e AWS_DEFAULT_REGION=sa-east-1 \\
      <image> python -m utils.dm_test_api_keys
"""

import argparse
import logging
import time
import requests
from dataclasses import dataclass, field
from typing import Optional

from web3 import Web3
from web3.exceptions import Web3Exception

from utils.dm_parameter_store import ParameterStoreClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test-api-keys")

# ---------------------------------------------------------------------------
# Resultado por chave
# ---------------------------------------------------------------------------

@dataclass
class KeyTestResult:
    name: str
    vendor: str
    status: str = "PENDING"   # OK | FAIL | SKIP
    block_number: Optional[int] = None
    num_reqs: int = 0
    elapsed_sec: float = 0.0
    error: str = ""

    @property
    def rps(self) -> float:
        return round(self.num_reqs / self.elapsed_sec, 2) if self.elapsed_sec > 0 else 0.0


# ---------------------------------------------------------------------------
# Testes por vendor
# ---------------------------------------------------------------------------

VENDOR_URL = {
    "infura":  "https://{network}.infura.io/v3/{key}",
    "alchemy": "https://eth-{network}.g.alchemy.com/v2/{key}",
}

ETHERSCAN_URL = "https://api.etherscan.io/api"


def _detect_vendor(name: str) -> Optional[str]:
    """Infere o vendor a partir do nome do parâmetro no SSM."""
    n = name.lower()
    for vendor in ("infura", "alchemy", "etherscan"):
        if vendor in n:
            return vendor
    return None


def _test_web3_key(key_name: str, key_value: str, vendor: str, network: str, num_reqs: int) -> KeyTestResult:
    result = KeyTestResult(name=key_name, vendor=vendor, num_reqs=num_reqs)
    url = VENDOR_URL[vendor].format(network=network, key=key_value)
    try:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            result.status = "FAIL"
            result.error = "w3.is_connected() returned False"
            return result

        start = time.time()
        last_block = None
        for i in range(num_reqs):
            blk = w3.eth.get_block("latest")
            last_block = blk["number"]
        result.elapsed_sec = time.time() - start
        result.block_number = last_block
        result.status = "OK"
    except Web3Exception as exc:
        result.status = "FAIL"
        result.error = str(exc)
    except Exception as exc:
        result.status = "FAIL"
        result.error = str(exc)
    return result


def _test_etherscan_key(key_name: str, key_value: str) -> KeyTestResult:
    result = KeyTestResult(name=key_name, vendor="etherscan", num_reqs=1)
    try:
        start = time.time()
        resp = requests.get(
            ETHERSCAN_URL,
            params={"module": "stats", "action": "ethsupply", "apikey": key_value},
            timeout=10,
        )
        result.elapsed_sec = time.time() - start
        data = resp.json()
        if data.get("status") == "1":
            result.status = "OK"
        else:
            result.status = "FAIL"
            result.error = data.get("message", "Unknown error")
    except Exception as exc:
        result.status = "FAIL"
        result.error = str(exc)
    return result


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------

class APIKeysTester:

    def __init__(self, region: str = "sa-east-1", network: str = "mainnet", num_reqs: int = 5):
        self._ssm = ParameterStoreClient(region_name=region)
        self.network = network
        self.num_reqs = num_reqs
        self.results: list[KeyTestResult] = []

    def _fetch_api_keys(self) -> dict[str, str]:
        """Retorna todos os parâmetros do SSM cujo nome contenha 'api-key'."""
        logger.info("Buscando parâmetros no SSM Parameter Store…")
        all_params = self._ssm.list_parameters()
        api_keys = {k: v for k, v in all_params.items() if "api-key" in k.lower()}
        logger.info(f"Encontrados {len(api_keys)} parâmetros de API Key no SSM.")
        return api_keys

    def run(self) -> list[KeyTestResult]:
        api_keys = self._fetch_api_keys()

        for name, value in sorted(api_keys.items()):
            vendor = _detect_vendor(name)
            if vendor is None:
                logger.warning(f"  SKIP  {name}  (vendor não reconhecido)")
                self.results.append(KeyTestResult(name=name, vendor="unknown", status="SKIP"))
                continue

            logger.info(f"  Testando  {name}  [{vendor}]…")

            if vendor == "etherscan":
                r = _test_etherscan_key(name, value)
            elif vendor in VENDOR_URL:
                r = _test_web3_key(name, value, vendor, self.network, self.num_reqs)
            else:
                r = KeyTestResult(name=name, vendor=vendor, status="SKIP", error="vendor sem handler")

            status_label = "✅ OK  " if r.status == "OK" else ("⚠️ SKIP" if r.status == "SKIP" else "❌ FAIL")
            logger.info(f"         {status_label}  block={r.block_number}  {r.num_reqs} reqs  {r.elapsed_sec:.2f}s  {r.rps} RPS  err='{r.error}'")
            self.results.append(r)

        return self.results

    def print_summary(self) -> None:
        ok   = [r for r in self.results if r.status == "OK"]
        fail = [r for r in self.results if r.status == "FAIL"]
        skip = [r for r in self.results if r.status == "SKIP"]

        col = 40
        sep = "-" * 80
        print(f"\n{sep}")
        print(f"{'RESULTADO DOS TESTES DE API KEYS':^80}")
        print(sep)
        print(f"  {'NOME':<{col}} {'VENDOR':<12} {'STATUS':<6}  {'BLOCO':>10}  {'RPS':>7}  ERRO")
        print(sep)
        for r in sorted(self.results, key=lambda x: x.name):
            icon = " OK" if r.status == "OK" else ("SKP" if r.status == "SKIP" else "ERR")
            blk  = str(r.block_number) if r.block_number else "-"
            rps  = f"{r.rps:.1f}" if r.status == "OK" else "-"
            err  = r.error[:35] if r.error else ""
            print(f"  {r.name:<{col}} {r.vendor:<12} {icon:<6}  {blk:>10}  {rps:>7}  {err}")
        print(sep)
        print(f"  Total: {len(self.results)}  ✅ OK={len(ok)}  ❌ FAIL={len(fail)}  ⚠️ SKIP={len(skip)}")
        print(sep)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testa API Keys presentes no AWS SSM Parameter Store.")
    parser.add_argument("--region",    default="sa-east-1", help="Região AWS (default: sa-east-1)")
    parser.add_argument("--network",   default="mainnet",   help="Rede Ethereum (default: mainnet)")
    parser.add_argument("--num-reqs",  type=int, default=5, help="Número de requisições por chave Web3 (default: 5)")
    args = parser.parse_args()

    tester = APIKeysTester(region=args.region, network=args.network, num_reqs=args.num_reqs)
    tester.run()
    tester.print_summary()







        