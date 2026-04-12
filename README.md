# OracleForge

**Multi-Source Price Oracle** -- Cross-verified crypto & stock prices with confidence scoring and circuit breakers.

Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab.

## Features

- **5 Sources** -- CoinGecko, Pyth Network, Chainlink (on-chain), Finnhub, Yahoo Finance
- **Confidence Scoring** -- Cross-verification between sources, 0-1 confidence score
- **Circuit Breaker** -- Per-source failure isolation with auto-recovery
- **Batch Pricing** -- Up to 50 symbols in one request
- **Anomaly Detection** -- Flags when sources diverge significantly
- **Stocks + Crypto** -- Unified API for both asset classes

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8003 --reload
```

## API

```bash
# Single price with confidence
curl http://localhost:8003/api/price/BTC
# {"symbol":"BTC","price_usd":67234.5,"confidence":0.95,"sources_used":3}

# Batch pricing
curl -X POST http://localhost:8003/api/prices/batch \
  -d '{"symbols": ["BTC","ETH","SOL"]}'

# Source health
curl http://localhost:8003/api/sources
```

## Tech Stack

Python 3.12, FastAPI, httpx. 22 tests. Proprietary license.
