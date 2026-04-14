"""Base-mainnet on-chain verifier for x402 payments (Phase 4).

Extraction origin: MAXIA V12/backend/blockchain/base_verifier.py (303 lines).
This port keeps the same verification logic and the same fallback strategy
(try the Coinbase x402 facilitator first, fall back to a direct RPC read of
the user-supplied transaction hash) but adapts the module to MAXIA Oracle's
conventions:

    - `safe_error(context, exc, logger)` returns a client-safe string instead
      of a dict (Phase 2 signature, versus V12's error_utils signature)
    - Configuration is imported from `core.config` (our Phase 1 module) rather
      than MAXIA V12 core.config
    - No dependency on `core.http_client` yet — a local `httpx.AsyncClient` is
      used per module. Step 5 will refactor all oracle services and this file
      to share a singleton pool.

The verifier never holds a private key. It only reads on-chain state via
public Base-mainnet JSON-RPC endpoints to confirm that an incoming USDC
transfer reached our treasury address.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Final

import httpx

from core.config import (
    BASE_CHAIN_ID,
    BASE_MIN_TX_USDC,
    BASE_RPC_URLS,
    BASE_USDC_CONTRACT,
    IS_NON_DEV,
    X402_FACILITATOR_URL,
    X402_TREASURY_ADDRESS_BASE,
)
from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("maxia_oracle.x402.base_verifier")


# ── Module-level invariants ─────────────────────────────────────────────────

# Canonical USDC on Base mainnet per Coinbase docs. Pinned at module load
# time so a typo in BASE_USDC_CONTRACT (e.g. via env override) is detected
# before the first request.
_CANONICAL_USDC_BASE: Final[str] = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
if BASE_USDC_CONTRACT.lower() != _CANONICAL_USDC_BASE.lower():
    logger.critical(
        "[base_verifier] BASE_USDC_CONTRACT mismatch. Got %s, expected %s. "
        "Payment verification will reject every transfer.",
        BASE_USDC_CONTRACT,
        _CANONICAL_USDC_BASE,
    )

# The facilitator URL is already validated as HTTPS in core.config when
# IS_NON_DEV is true, but re-emit a runtime warning in dev if an operator
# sets an insecure override.
if not X402_FACILITATOR_URL.startswith("https://") and not IS_NON_DEV:
    logger.warning(
        "[base_verifier] X402_FACILITATOR_URL is not HTTPS in dev: %s. "
        "Staging/prod would have refused to start.",
        X402_FACILITATOR_URL,
    )


# ── RPC rate limiter ─────────────────────────────────────────────────────────
#
# Defensive cap on outbound RPC calls to protect the public endpoints from
# being abused. This is a per-process in-memory limit — Phase 7 can move it
# to Redis if the service scales horizontally.

_RPC_CALL_LIMIT_PER_MINUTE: Final[int] = 100
_rpc_call_timestamps: list[float] = []
_rpc_lock = asyncio.Lock()


async def _check_rpc_rate_limit() -> None:
    """Enforce the per-process RPC quota. Raises RuntimeError if exceeded."""
    async with _rpc_lock:
        now = time.monotonic()
        cutoff = now - 60.0
        while _rpc_call_timestamps and _rpc_call_timestamps[0] < cutoff:
            _rpc_call_timestamps.pop(0)
        if len(_rpc_call_timestamps) >= _RPC_CALL_LIMIT_PER_MINUTE:
            raise RuntimeError(
                f"RPC rate limit exceeded ({_RPC_CALL_LIMIT_PER_MINUTE} calls/min)"
            )
        _rpc_call_timestamps.append(now)


# The HTTP client is the process-wide singleton exported by
# `core.http_client`. Its shutdown is handled in the FastAPI lifespan via
# `core.http_client.close_http_client`, not here.


# ── RPC primitive with multi-URL fallback ────────────────────────────────────

async def _rpc_post(payload: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    """POST a JSON-RPC request to the configured Base RPC endpoints.

    Tries each entry in BASE_RPC_URLS in order and returns the first successful
    JSON response. Raises the last encountered error if every endpoint fails.
    """
    await _check_rpc_rate_limit()

    last_error: Exception | None = None
    client = get_http_client()
    for rpc_url in BASE_RPC_URLS:
        try:
            resp = await client.post(rpc_url, json=payload, timeout=timeout)
            data = resp.json()
            if data.get("error"):
                logger.warning(
                    "[base_verifier] RPC %s returned error: %s", rpc_url, data["error"]
                )
                last_error = RuntimeError(f"RPC error from {rpc_url}")
                continue
            return data
        except httpx.TimeoutException as exc:
            logger.warning("[base_verifier] RPC %s timeout", rpc_url)
            last_error = exc
        except httpx.ConnectError as exc:
            logger.warning("[base_verifier] RPC %s connect error", rpc_url)
            last_error = exc
        except Exception as exc:
            logger.warning(
                "[base_verifier] RPC %s unexpected %s", rpc_url, type(exc).__name__
            )
            last_error = exc

    raise last_error or RuntimeError("All Base RPC endpoints failed")


# ── Public verification helpers ─────────────────────────────────────────────

_TX_HASH_LENGTH: Final[int] = 66  # "0x" + 64 hex chars
_USDC_TRANSFER_TOPIC: Final[str] = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


def _is_valid_tx_hash(value: str) -> bool:
    """Return True iff `value` matches the canonical Ethereum tx-hash format."""
    if not isinstance(value, str) or len(value) != _TX_HASH_LENGTH:
        return False
    if not value.startswith("0x"):
        return False
    try:
        int(value[2:], 16)
    except ValueError:
        return False
    return True


async def verify_base_transaction(
    tx_hash: str, expected_to: str | None = None
) -> dict[str, Any]:
    """Verify that `tx_hash` is a successful transaction on Base mainnet.

    Calls `eth_getTransactionReceipt` and checks the status bit. If
    `expected_to` is provided, the recipient of the outer tx is compared
    against it (case-insensitive). Returns a dict shaped like:

        {
          "valid": True,
          "blockNumber": int,
          "from": "0x...",
          "to": "0x...",
          "gasUsed": int,
          "network": "base-mainnet",
          "chainId": 8453,
        }

    or `{"valid": False, "error": "..."}` on any failure.
    """
    if not _is_valid_tx_hash(tx_hash):
        return {"valid": False, "error": "invalid tx_hash format"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
    }

    for attempt in range(3):
        try:
            data = await _rpc_post(payload)
            result = data.get("result")
            if not result:
                # Transaction not yet mined — back off and retry.
                await asyncio.sleep(2**attempt)
                continue
            if result.get("status") != "0x1":
                return {"valid": False, "error": "transaction reverted"}
            if expected_to and result.get("to", "").lower() != expected_to.lower():
                return {"valid": False, "error": "recipient mismatch"}
            logger.info(
                "[base_verifier] TX verified: %s... block=%s",
                tx_hash[:16],
                result.get("blockNumber"),
            )
            return {
                "valid": True,
                "blockNumber": int(result.get("blockNumber", "0x0"), 16),
                "from": result.get("from", ""),
                "to": result.get("to", ""),
                "gasUsed": int(result.get("gasUsed", "0x0"), 16),
                "network": "base-mainnet",
                "chainId": BASE_CHAIN_ID,
            }
        except RuntimeError as exc:
            # Rate-limit exceeded — fail fast without retrying.
            return {
                "valid": False,
                "error": safe_error("base_verify_tx rate-limited", exc, logger),
            }
        except httpx.TimeoutException:
            logger.warning(
                "[base_verifier] verify_base_transaction attempt %d timeout", attempt + 1
            )
            await asyncio.sleep(2**attempt)
        except httpx.ConnectError:
            logger.warning(
                "[base_verifier] verify_base_transaction attempt %d connect error",
                attempt + 1,
            )
            await asyncio.sleep(2**attempt)
        except Exception as exc:
            logger.error(
                "[base_verifier] verify_base_transaction attempt %d failed: %s",
                attempt + 1,
                type(exc).__name__,
                exc_info=True,
            )
            await asyncio.sleep(2**attempt)

    return {"valid": False, "error": "verification failed after retries"}


async def verify_usdc_transfer_base(
    tx_hash: str,
    expected_amount_raw: int | None = None,
    expected_recipient: str | None = None,
) -> dict[str, Any]:
    """Verify that `tx_hash` emitted a USDC ERC-20 Transfer event to our treasury.

    `expected_amount_raw` is in USDC atomic units (6 decimals, so 0.001 USDC
    = 1000). If omitted, the minimum acceptable amount defaults to
    BASE_MIN_TX_USDC.

    Returns a dict with a `"usdcTransfer"` sub-dict on success, or
    `{"valid": False, "error": "..."}` on any failure.
    """
    if expected_recipient is None:
        if not X402_TREASURY_ADDRESS_BASE:
            return {
                "valid": False,
                "error": "X402_TREASURY_ADDRESS_BASE not configured",
            }
        expected_recipient = X402_TREASURY_ADDRESS_BASE

    if expected_amount_raw is not None and expected_amount_raw > 0:
        min_raw = int(BASE_MIN_TX_USDC * 1_000_000)
        if expected_amount_raw < min_raw:
            return {
                "valid": False,
                "error": (
                    f"amount below minimum: ${expected_amount_raw / 1e6:.4f} "
                    f"< ${BASE_MIN_TX_USDC}"
                ),
            }

    receipt = await verify_base_transaction(tx_hash, expected_to=None)
    if not receipt.get("valid"):
        return receipt

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
    }

    try:
        data = await _rpc_post(payload)
        logs = data.get("result", {}).get("logs", [])
        for log in logs:
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue
            if (
                log.get("address", "").lower() != BASE_USDC_CONTRACT.lower()
                or topics[0] != _USDC_TRANSFER_TOPIC
            ):
                continue
            # Topics[1] = from (padded 32 bytes), Topics[2] = to (padded 32 bytes).
            # ERC-20 Transfer addresses are the last 40 hex chars of the topic.
            if len(topics[1]) < 42 or len(topics[2]) < 42:
                logger.warning(
                    "[base_verifier] Malformed Transfer topics in %s", tx_hash
                )
                continue

            amount = int(log.get("data", "0x0"), 16)
            from_addr = "0x" + topics[1][-40:]
            to_addr = "0x" + topics[2][-40:]

            if to_addr.lower() != expected_recipient.lower():
                return {
                    "valid": False,
                    "error": f"recipient mismatch: {to_addr} != {expected_recipient}",
                }

            if expected_amount_raw and amount < expected_amount_raw:
                return {
                    "valid": False,
                    "error": (
                        f"insufficient amount: {amount / 1e6:.6f} USDC "
                        f"< {expected_amount_raw / 1e6:.6f} USDC"
                    ),
                }

            receipt["usdcTransfer"] = {
                "from": from_addr,
                "to": to_addr,
                "amount_raw": amount,
                "amount_usdc": amount / 1_000_000,
            }
            logger.info(
                "[base_verifier] USDC transfer verified: %s... %s...->%s... %.6f USDC",
                tx_hash[:16],
                from_addr[:10],
                to_addr[:10],
                amount / 1_000_000,
            )
            return receipt

        return {"valid": False, "error": "no USDC Transfer event found in logs"}

    except RuntimeError as exc:
        return {
            "valid": False,
            "error": safe_error("base_verify_usdc rate-limited", exc, logger),
        }
    except httpx.TimeoutException as exc:
        return {
            "valid": False,
            "error": safe_error("base_verify_usdc timeout", exc, logger),
        }
    except httpx.ConnectError as exc:
        return {
            "valid": False,
            "error": safe_error("base_verify_usdc connect error", exc, logger),
        }
    except Exception as exc:
        return {
            "valid": False,
            "error": safe_error("base_verify_usdc failed", exc, logger),
        }


async def x402_verify_payment_base(
    payment_header: str, expected_amount_usdc: float
) -> dict[str, Any]:
    """Verify an x402 payment on Base via the Coinbase facilitator with on-chain fallback.

    Strategy:
        1. POST the payment payload to `X402_FACILITATOR_URL/verify`. The
           facilitator supports the canonical x402-v2 signed payload format.
        2. If the facilitator times out, errors, or rejects, treat the
           `payment_header` as a raw tx hash and perform a direct on-chain
           USDC transfer verification against our treasury.

    Returns `{"valid": True, ...}` on success or
    `{"valid": False, "error": "..."}` on any failure.
    """
    # First try: the Coinbase facilitator.
    try:
        client = get_http_client()
        resp = await client.post(
            f"{X402_FACILITATOR_URL}/verify",
            json={
                "paymentPayload": payment_header,
                "network": "base-mainnet",
                "expectedAmount": str(int(expected_amount_usdc * 1_000_000)),
            },
            timeout=20.0,
        )
        facilitator_result = resp.json() if resp.status_code == 200 else {}
        if resp.status_code == 200 and facilitator_result.get("valid"):
            tx_hash = facilitator_result.get("txHash", "")
            logger.info(
                "[x402] Base payment verified via facilitator: %s...", tx_hash[:16]
            )
            return {
                "valid": True,
                "txHash": tx_hash,
                "network": "base-mainnet",
                "settledAmount": facilitator_result.get("settledAmount"),
                "verifiedVia": "facilitator",
            }
        logger.warning(
            "[x402] Facilitator rejected payment: %s",
            facilitator_result.get("error", "unknown"),
        )
    except httpx.TimeoutException:
        logger.warning("[x402] Facilitator timeout — trying on-chain fallback")
    except httpx.ConnectError:
        logger.warning("[x402] Facilitator connect error — trying on-chain fallback")
    except Exception as exc:
        logger.warning(
            "[x402] Facilitator unexpected %s — trying on-chain fallback",
            type(exc).__name__,
        )

    # Fallback: treat payment_header as a raw tx hash and verify on-chain.
    if _is_valid_tx_hash(payment_header):
        logger.info(
            "[x402] Attempting direct on-chain fallback for %s...", payment_header[:16]
        )
        direct_result = await verify_usdc_transfer_base(
            tx_hash=payment_header,
            expected_amount_raw=int(expected_amount_usdc * 1_000_000),
        )
        if direct_result.get("valid"):
            direct_result["verifiedVia"] = "direct-onchain-fallback"
            direct_result["txHash"] = payment_header
            logger.info(
                "[x402] Direct on-chain verification succeeded for %s...",
                payment_header[:16],
            )
            return direct_result
        logger.warning(
            "[x402] Direct on-chain fallback failed: %s",
            direct_result.get("error"),
        )

    return {
        "valid": False,
        "error": "facilitator rejected and direct verification failed",
    }


def build_x402_challenge_base(path: str, price_usdc: float, pay_to: str) -> dict[str, Any]:
    """Construct a single `accepts` entry for a 402 response on Base mainnet."""
    return {
        "scheme": "exact",
        "network": "base-mainnet",
        "maxAmountRequired": str(int(price_usdc * 1_000_000)),
        "resource": path,
        "description": f"MAXIA Oracle: {path}",
        "mimeType": "application/json",
        "payTo": pay_to,
        "asset": BASE_USDC_CONTRACT,
        "maxTimeoutSeconds": 60,
        "extra": {
            "chainId": BASE_CHAIN_ID,
            "facilitator": X402_FACILITATOR_URL,
        },
    }
