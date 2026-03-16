"""

Reads env var KAFKA_MSK_IAM ("true"/"false"). When enabled, returns a config
dict with security.protocol=SASL_SSL and an OAuth callback that generates
short-lived MSK IAM tokens via aws-msk-iam-sasl-signer-python.

Usage:
    from dm_chain_utils.dm_msk_iam import get_msk_iam_config
    conf = {**base_kafka_conf, **get_msk_iam_config()}

Requires (when KAFKA_MSK_IAM=true):
    pip install aws-msk-iam-sasl-signer-python>=1.0.2
"""

import os
from typing import Dict, Tuple


def get_msk_iam_config() -> Dict:
    """Returns confluent-kafka config for MSK IAM SASL/SSL auth.

    When KAFKA_MSK_IAM env var is not 'true' (e.g. DEV with local Kafka),
    returns an empty dict so callers work without any code changes.
    """
    if os.getenv("KAFKA_MSK_IAM", "false").lower() != "true":
        return {}

    region = os.getenv("AWS_DEFAULT_REGION", "sa-east-1")

    def _oauth_cb(oauth_config) -> Tuple[str, float]:  # noqa: ARG001
        from aws_msk_iam_sasl_signer import MSKAuthTokenProvider  # lazy import; not needed in DEV

        token, expiry_ms = MSKAuthTokenProvider.generate_auth_token(region)
        return token, expiry_ms / 1000.0  # confluent-kafka expects seconds

    return {
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "OAUTHBEARER",
        "oauth_cb": _oauth_cb,
    }
