# DataForge

**Structured AI Data API** — news sentiment, on-chain events, structured market data. Complements OracleForge (prices) with qualitative data.

Part of the [Forge Suite](https://maxiaworld.app) by MAXIA Lab.

## Status

🚧 **In development** — extracted from MAXIA V12

## Source modules (MAXIA V12)

- `backend/ai/sentiment_analyzer.py`
- `backend/features/data_marketplace.py`
- `backend/marketplace/data_marketplace.py`

## Planned features

- `GET /data/sentiment?asset=BTC` — sentiment score + sources
- `GET /data/news?asset=ETH&limit=20` — curated news feed
- `GET /data/events/onchain?chain=ethereum` — on-chain events (transfers, governance, liquidations)
- `GET /data/summary/{asset}` — combined sentiment + news + events digest

## Stack

- Backend: Python 3.12 + FastAPI, port 8010
- Domain: data.maxiaworld.app
