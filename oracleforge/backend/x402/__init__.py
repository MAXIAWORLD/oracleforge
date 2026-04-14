"""MAXIA Oracle — x402 micropayment module (Phase 4).

This package implements the x402 direct-sale payment path for MAXIA Oracle on
Base mainnet. An AI agent pays a fixed USDC amount to our public treasury
wallet, the middleware verifies the on-chain transaction, and the protected
route is served in the same request cycle.

Non-goals:
    - No escrow, no multi-party settlement, no intermediation
    - No custody of agent funds
    - No signing of outbound transactions (the service never holds a private key)
    - No cross-chain swap or bridging

Extraction origin: MAXIA V12 supported 14 chains via a single middleware and
14 verifier modules. MAXIA Oracle V1 keeps only the Base-mainnet verifier and
middleware path, reducing the attack surface by ~93% and dropping all
blockchain SDK dependencies (web3.py, solders, xrpl-py, etc.).
"""
