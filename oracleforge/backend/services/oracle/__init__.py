"""Multi-source price oracle — extracted from MAXIA V12 on 2026-04-14.

Modules:
    pyth_oracle         — Pyth Network Hermes API + SSE streaming (crypto + equities)
    pyth_solana_oracle  — Pyth native Solana on-chain (V1.4, Price Feed Accounts shard 0)
    chainlink_oracle    — Chainlink on-chain (Base + Ethereum + Arbitrum)
    redstone_oracle     — RedStone public REST (V1.3, 4th upstream)
    price_oracle        — Helius DAS + CoinPaprika + CoinGecko + Yahoo Finance

Public entrypoints (stable across phases):
    pyth_oracle.get_pyth_price(feed_id)              — single Pyth feed (Hermes)
    pyth_oracle.get_batch_prices(symbols)            — Pyth batch (crypto + equity)
    pyth_oracle.get_crypto_price(symbol)             — Pyth -> CoinGecko cascade
    pyth_oracle.get_stock_price(symbol)              — Pyth -> Finnhub -> CoinGecko -> Yahoo
    pyth_solana_oracle.get_pyth_solana_price(symbol) — on-chain Solana read (V1.4)
    chainlink_oracle.get_chainlink_price()           — on-chain eth_call
    chainlink_oracle.verify_price_chainlink()        — cross-verification
    redstone_oracle.get_redstone_price()             — RedStone public REST (V1.3)
    price_oracle.get_prices(symbols=None)            — Helius + CoinPaprika + CoinGecko
    price_oracle.get_crypto_prices()                 — crypto subset
    price_oracle.get_stock_prices()                  — Pyth -> Yahoo -> Finnhub cascade
"""
