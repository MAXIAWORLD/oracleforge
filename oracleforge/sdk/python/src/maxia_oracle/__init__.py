"""MAXIA Oracle — Python SDK.

Data feed only. Not investment advice. No custody. No KYC.

Quick start:

    from maxia_oracle import MaxiaOracleClient

    with MaxiaOracleClient(api_key="mxo_...") as client:
        print(client.price("BTC"))
"""
from __future__ import annotations

from .client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_S, MaxiaOracleClient
from .exceptions import (
    MaxiaOracleAuthError,
    MaxiaOracleError,
    MaxiaOraclePaymentRequiredError,
    MaxiaOracleRateLimitError,
    MaxiaOracleTransportError,
    MaxiaOracleUpstreamError,
    MaxiaOracleValidationError,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_S",
    "MaxiaOracleClient",
    "MaxiaOracleError",
    "MaxiaOracleAuthError",
    "MaxiaOraclePaymentRequiredError",
    "MaxiaOracleRateLimitError",
    "MaxiaOracleUpstreamError",
    "MaxiaOracleValidationError",
    "MaxiaOracleTransportError",
]
