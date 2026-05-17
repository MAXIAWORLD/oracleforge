"""Generic EVM USDC verifier for x402 — V1.2 multi-chain.

Every supported chain (Base, Arbitrum, Optimism, Polygon) speaks the same
ERC-20 `Transfer` event, exposes the same `eth_getTransactionReceipt` RPC
shape and uses USDC with 6 decimals. This module factors the chain-agnostic
verification logic out of the Phase 4 `base_verifier.py`, so adding a new
chain is just a matter of extending `X402_CHAIN_CONFIG` in `core.config`.

Responsibilities:
    1. `verify_usdc_transfer(chain, tx_hash, ...)` — read a receipt on
       `chain`, confirm the tx succeeded, confirm a USDC ERC-20 Transfer
       went to our treasury for at least the expected amount.
    2. `x402_verify_payment(chain, header, amount)` — dispatch. Base
       still tries the Coinbase facilitator first (official x402-v2
       support) then falls back on-chain. The three other chains go
       direct on-chain.
    3. `build_x402_challenge(chain, path, price)` — build one 402
       `accepts` entry for one chain.
    4. `build_all_accepts(path, price)` — build the list of accepts
       entries for every chain that has a treasury configured.

The module never holds a private key. It only reads public RPC endpoints
to confirm that incoming USDC transfers reached our treasury.

Data feed only. Not investment advice. No custody. No KYC.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Final

import httpx

from core.config import (
    BASE_MIN_TX_USDC,
    CHAIN_RPC_URLS,
    IS_NON_DEV,
    X402_CHAIN_CONFIG,
    X402_FACILITATOR_URL,
    X402_SUPPORTED_CHAINS,
)
from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("maxia_oracle.x402.multichain")


# ── Module-level invariants ─────────────────────────────────────────────────

# Canonical USDC ERC-20 Transfer topic (first 32 bytes of keccak256
# "Transfer(address,address,uint256)"). Identical on every EVM chain.
_USDC_TRANSFER_TOPIC: Final[str] = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)

# USDC has 6 decimals on every chain in X402_SUPPORTED_CHAINS. Multiplying
# a USD amount by this constant yields atomic units used in on-chain
# comparisons.
_USDC_ATOMIC_PER_WHOLE: Final[int] = 1_000_000

# "0x" + 64 hex chars = canonical EVM tx hash.
_TX_HASH_LENGTH: Final[int] = 66

# Defensive per-process RPC rate limit (see base_verifier.py for rationale).
_RPC_CALL_LIMIT_PER_MINUTE: Final[int] = 100
_rpc_call_timestamps: list[float] = []
_rpc_lock = asyncio.Lock()


if not X402_FACILITATOR_URL.startswith("https://") and not IS_NON_DEV:
    logger.warning(
        "[multichain_verifier] X402_FACILITATOR_URL is not HTTPS in dev: %s. "
        "Staging/prod would have refused to start.",
        X402_FACILITATOR_URL,
    )


# ── Internal helpers ────────────────────────────────────────────────────────


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


def _is_valid_tx_hash(value: str) -> bool:
    """Return True iff `value` matches the canonical EVM tx-hash format."""
    if not isinstance(value, str) or len(value) != _TX_HASH_LENGTH:
        return False
    if not value.startswith("0x"):
        return False
    try:
        int(value[2:], 16)
    except ValueError:
        return False
    return True


def _is_supported_chain(chain: str) -> bool:
    return chain in X402_SUPPORTED_CHAINS


async def _rpc_post(
    chain: str, payload: dict[str, Any], timeout: float = 20.0
) -> dict[str, Any]:
    """POST a JSON-RPC request to `chain`'s RPC fallback pool.

    Tries every entry in `CHAIN_RPC_URLS[chain]` in order and returns the
    first successful JSON response. Raises the last encountered error if
    every endpoint fails.
    """
    if chain not in CHAIN_RPC_URLS:
        raise ValueError(f"no RPC pool configured for chain {chain!r}")

    await _check_rpc_rate_limit()

    last_error: Exception | None = None
    client = get_http_client()
    for rpc_url in CHAIN_RPC_URLS[chain]:
        try:
            resp = await client.post(rpc_url, json=payload, timeout=timeout)
            data = resp.json()
            if data.get("error"):
                logger.warning(
                    "[%s] RPC %s returned error: %s",
                    chain,
                    rpc_url,
                    data["error"],
                )
                last_error = RuntimeError(f"RPC error from {rpc_url}")
                continue
            return data
        except httpx.TimeoutException as exc:
            logger.warning("[%s] RPC %s timeout", chain, rpc_url)
            last_error = exc
        except httpx.ConnectError as exc:
            logger.warning("[%s] RPC %s connect error", chain, rpc_url)
            last_error = exc
        except Exception as exc:
            logger.warning(
                "[%s] RPC %s unexpected %s",
                chain,
                rpc_url,
                type(exc).__name__,
            )
            last_error = exc

    raise last_error or RuntimeError(f"All {chain} RPC endpoints failed")


# ── Public helpers ──────────────────────────────────────────────────────────


async def verify_evm_transaction(
    chain: str, tx_hash: str, expected_to: str | None = None
) -> dict[str, Any]:
    """Verify that `tx_hash` is a successful tx on `chain`.

    Calls `eth_getTransactionReceipt`, checks the status bit, optionally
    compares the recipient. Returns:
        {"valid": True, "blockNumber": int, "from": str, "to": str,
         "gasUsed": int, "network": str, "chainId": int}
    or `{"valid": False, "error": "..."}` on any failure.
    """
    if not _is_supported_chain(chain):
        return {"valid": False, "error": f"unsupported chain: {chain}"}
    if not _is_valid_tx_hash(tx_hash):
        return {"valid": False, "error": "invalid tx_hash format"}

    cfg = X402_CHAIN_CONFIG[chain]

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
    }

    for attempt in range(3):
        try:
            data = await _rpc_post(chain, payload)
            result = data.get("result")
            if not result:
                await asyncio.sleep(2**attempt)
                continue
            if result.get("status") != "0x1":
                return {"valid": False, "error": "transaction reverted"}
            if expected_to and result.get("to", "").lower() != expected_to.lower():
                return {"valid": False, "error": "recipient mismatch"}
            logger.info(
                "[%s] TX verified: %s... block=%s",
                chain,
                tx_hash[:16],
                result.get("blockNumber"),
            )
            return {
                "valid": True,
                "blockNumber": int(result.get("blockNumber", "0x0"), 16),
                "from": result.get("from", ""),
                "to": result.get("to", ""),
                "gasUsed": int(result.get("gasUsed", "0x0"), 16),
                "network": cfg["network_label"],
                "chainId": cfg["chain_id"],
            }
        except RuntimeError as exc:
            return {
                "valid": False,
                "error": safe_error(f"{chain} verify_tx rate-limited", exc, logger),
            }
        except httpx.TimeoutException:
            logger.warning("[%s] verify_evm_transaction attempt %d timeout", chain, attempt + 1)
            await asyncio.sleep(2**attempt)
        except httpx.ConnectError:
            logger.warning(
                "[%s] verify_evm_transaction attempt %d connect error", chain, attempt + 1
            )
            await asyncio.sleep(2**attempt)
        except Exception as exc:
            logger.error(
                "[%s] verify_evm_transaction attempt %d failed: %s",
                chain,
                attempt + 1,
                type(exc).__name__,
                exc_info=True,
            )
            await asyncio.sleep(2**attempt)

    return {"valid": False, "error": "verification failed after retries"}


async def verify_usdc_transfer(
    chain: str,
    tx_hash: str,
    expected_amount_raw: int | None = None,
    expected_recipient: str | None = None,
) -> dict[str, Any]:
    """Verify that `tx_hash` emitted a USDC ERC-20 Transfer to our treasury on `chain`.

    `expected_amount_raw` is in USDC atomic units (6 decimals, so 0.001
    USDC = 1000). Defaults to the min tx amount in BASE_MIN_TX_USDC
    (applied uniformly across chains in V1.2).

    Returns `{"valid": True, "usdcTransfer": {...}, ...}` on success or
    `{"valid": False, "error": "..."}` on any failure.
    """
    if not _is_supported_chain(chain):
        return {"valid": False, "error": f"unsupported chain: {chain}"}

    cfg = X402_CHAIN_CONFIG[chain]
    treasury = cfg["treasury"]
    usdc_contract = cfg["usdc_contract"]

    if expected_recipient is None:
        if not treasury:
            return {
                "valid": False,
                "error": f"treasury address not configured for {chain}",
            }
        expected_recipient = treasury

    if expected_amount_raw is not None and expected_amount_raw > 0:
        min_raw = int(BASE_MIN_TX_USDC * _USDC_ATOMIC_PER_WHOLE)
        if expected_amount_raw < min_raw:
            return {
                "valid": False,
                "error": (
                    f"amount below minimum: "
                    f"${expected_amount_raw / _USDC_ATOMIC_PER_WHOLE:.4f} "
                    f"< ${BASE_MIN_TX_USDC}"
                ),
            }

    receipt = await verify_evm_transaction(chain, tx_hash, expected_to=None)
    if not receipt.get("valid"):
        return receipt

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
    }

    try:
        data = await _rpc_post(chain, payload)
        logs = data.get("result", {}).get("logs", [])
        for log in logs:
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue
            if (
                log.get("address", "").lower() != usdc_contract.lower()
                or topics[0] != _USDC_TRANSFER_TOPIC
            ):
                continue
            if len(topics[1]) < 42 or len(topics[2]) < 42:
                logger.warning("[%s] Malformed Transfer topics in %s", chain, tx_hash)
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
                        f"insufficient amount: "
                        f"{amount / _USDC_ATOMIC_PER_WHOLE:.6f} USDC "
                        f"< {expected_amount_raw / _USDC_ATOMIC_PER_WHOLE:.6f} USDC"
                    ),
                }

            receipt["usdcTransfer"] = {
                "from": from_addr,
                "to": to_addr,
                "amount_raw": amount,
                "amount_usdc": amount / _USDC_ATOMIC_PER_WHOLE,
            }
            logger.info(
                "[%s] USDC transfer verified: %s... %s...->%s... %.6f USDC",
                chain,
                tx_hash[:16],
                from_addr[:10],
                to_addr[:10],
                amount / _USDC_ATOMIC_PER_WHOLE,
            )
            return receipt

        return {"valid": False, "error": "no USDC Transfer event found in logs"}

    except RuntimeError as exc:
        return {
            "valid": False,
            "error": safe_error(f"{chain} verify_usdc rate-limited", exc, logger),
        }
    except httpx.TimeoutException as exc:
        return {
            "valid": False,
            "error": safe_error(f"{chain} verify_usdc timeout", exc, logger),
        }
    except httpx.ConnectError as exc:
        return {
            "valid": False,
            "error": safe_error(f"{chain} verify_usdc connect error", exc, logger),
        }
    except Exception as exc:
        return {
            "valid": False,
            "error": safe_error(f"{chain} verify_usdc failed", exc, logger),
        }


async def _try_coinbase_facilitator_base(
    payment_header: str, expected_amount_usdc: float
) -> dict[str, Any] | None:
    """Try the Coinbase x402 facilitator for a Base-mainnet payment.

    Returns a success dict on valid, None on any failure (caller falls
    back to direct on-chain verification). Base-only: Coinbase does not
    publish a facilitator for the other supported chains in V1.2.
    """
    try:
        client = get_http_client()
        resp = await client.post(
            f"{X402_FACILITATOR_URL}/verify",
            json={
                "paymentPayload": payment_header,
                "network": "base-mainnet",
                "expectedAmount": str(
                    int(expected_amount_usdc * _USDC_ATOMIC_PER_WHOLE)
                ),
            },
            timeout=20.0,
        )
        body = resp.json() if resp.status_code == 200 else {}
        if resp.status_code == 200 and body.get("valid"):
            tx_hash = body.get("txHash", "")
            logger.info(
                "[x402] Base payment verified via facilitator: %s...", tx_hash[:16]
            )
            return {
                "valid": True,
                "txHash": tx_hash,
                "network": "base-mainnet",
                "settledAmount": body.get("settledAmount"),
                "verifiedVia": "facilitator",
                "chainId": X402_CHAIN_CONFIG["base"]["chain_id"],
            }
        logger.warning(
            "[x402] Facilitator rejected payment: %s",
            body.get("error", "unknown"),
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
    return None


async def x402_verify_payment(
    chain: str, payment_header: str, expected_amount_usdc: float
) -> dict[str, Any]:
    """Verify an x402 payment on `chain`.

    Strategy:
        - chain == "base": POST the payment header to the Coinbase
          facilitator first. On facilitator failure, fall back to a
          direct on-chain USDC transfer check against our treasury.
        - other chains: skip the facilitator (Coinbase is Base-only),
          go direct on-chain immediately.

    Returns `{"valid": True, ...}` on success, `{"valid": False,
    "error": "..."}` otherwise.
    """
    if not _is_supported_chain(chain):
        return {"valid": False, "error": f"unsupported chain: {chain}"}

    cfg = X402_CHAIN_CONFIG[chain]
    if not cfg["treasury"]:
        return {
            "valid": False,
            "error": f"no treasury configured for {chain}",
        }

    if chain == "base":
        facilitator_result = await _try_coinbase_facilitator_base(
            payment_header, expected_amount_usdc
        )
        if facilitator_result is not None:
            return facilitator_result

    if not _is_valid_tx_hash(payment_header):
        return {
            "valid": False,
            "error": "facilitator rejected and payment_header is not a valid tx_hash",
        }

    logger.info(
        "[%s] Attempting direct on-chain verification for %s...",
        chain,
        payment_header[:16],
    )
    direct = await verify_usdc_transfer(
        chain=chain,
        tx_hash=payment_header,
        expected_amount_raw=int(expected_amount_usdc * _USDC_ATOMIC_PER_WHOLE),
    )
    if direct.get("valid"):
        direct["verifiedVia"] = (
            "direct-onchain-fallback" if chain == "base" else "direct-onchain"
        )
        direct["txHash"] = payment_header
        logger.info(
            "[%s] Direct on-chain verification succeeded for %s...",
            chain,
            payment_header[:16],
        )
        return direct
    logger.warning(
        "[%s] Direct on-chain verification failed: %s",
        chain,
        direct.get("error"),
    )
    return {
        "valid": False,
        "error": direct.get("error") or "verification failed",
    }


# ── 402 challenge builders ──────────────────────────────────────────────────


def build_x402_challenge(
    chain: str, path: str, price_usdc: float
) -> dict[str, Any] | None:
    """Build a single 402 `accepts` entry for `chain`.

    Returns None if `chain` has no treasury configured — the caller drops
    the entry from the accepts array so the client only sees chains we
    can actually settle on.
    """
    if not _is_supported_chain(chain):
        return None
    cfg = X402_CHAIN_CONFIG[chain]
    if not cfg["treasury"]:
        return None

    extra: dict[str, Any] = {"chainId": cfg["chain_id"]}
    if cfg["facilitator"]:
        extra["facilitator"] = cfg["facilitator"]

    return {
        "scheme": "exact",
        "network": cfg["network_label"],
        "maxAmountRequired": str(int(price_usdc * _USDC_ATOMIC_PER_WHOLE)),
        "resource": path,
        "description": f"MAXIA Oracle: {path}",
        "mimeType": "application/json",
        "payTo": cfg["treasury"],
        "asset": cfg["usdc_contract"],
        "maxTimeoutSeconds": 60,
        "extra": extra,
    }


def build_all_accepts(path: str, price_usdc: float) -> list[dict[str, Any]]:
    """Build the list of accepts entries across every configured chain."""
    out: list[dict[str, Any]] = []
    for chain in X402_SUPPORTED_CHAINS:
        entry = build_x402_challenge(chain, path, price_usdc)
        if entry is not None:
            out.append(entry)
    return out
