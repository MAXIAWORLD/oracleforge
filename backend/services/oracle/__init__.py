"""Multi-source price oracle — extracted from MAXIA V12 on 2026-04-14.

6 upstream sources, 4 used for cross-validation in multi_source.collect_sources():
    ✓ pyth_oracle        — Pyth Network Hermes API (feeds, cache, single-price, TWAP)
    ✓ chainlink_oracle   — Chainlink on-chain (Base + Ethereum + Arbitrum)
    ✓ price_oracle       — Helius DAS + CoinPaprika + CoinGecko + Yahoo Finance
    ✓ redstone_oracle    — RedStone public REST (V1.3, 4th upstream)
    ✗ pyth_solana_oracle — excluded: same Pyth publishers as Hermes (would bias median)
    ✗ uniswap_v3_oracle  — excluded: TWAP ≠ spot (would corrupt divergence_pct)

Other modules:
    price_cascade       — Multi-source fallback chains (stock, crypto, batch)
    multi_source        — Cross-validation aggregator (median + divergence_pct)
    intelligence        — Confidence score, anomaly detection, context (V1.6)
    metadata            — CoinGecko asset metadata (market cap, volume, ATH…) (V1.7)

Public entrypoints (stable across phases):
    pyth_oracle.get_pyth_price(feed_id)              — single Pyth feed (Hermes)
    price_cascade.get_batch_prices(symbols)          — Pyth batch + CoinGecko fallback
    price_cascade.get_crypto_price(symbol)           — Pyth -> CoinGecko cascade
    price_cascade.get_stock_price(symbol)            — Pyth -> Finnhub -> CoinGecko -> Yahoo
    pyth_solana_oracle.get_pyth_solana_price(symbol) — on-chain Solana read (V1.4)
    chainlink_oracle.get_chainlink_price()           — on-chain eth_call
    chainlink_oracle.verify_price_chainlink()        — cross-verification
    redstone_oracle.get_redstone_price()             — RedStone public REST (V1.3)
    price_oracle.get_prices(symbols=None)            — Helius + CoinPaprika + CoinGecko
    price_oracle.get_crypto_prices()                 — crypto subset
    price_oracle.get_stock_prices()                  — Pyth -> Yahoo -> Finnhub cascade
"""
