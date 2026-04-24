# RelayForge

**Cross-Chain Message Relay** — AIP v0.3 signed envelopes, 15 chains supported. Authenticated cross-chain messaging, zero regulation.

Part of the [Forge Suite](https://maxiaworld.app) by MAXIA Lab.

## Status

🚧 **In development** — extracted from MAXIA V12

## Source modules (MAXIA V12)

- `backend/blockchain/cross_chain_handler.py`
- `demos/langchain_maxia_aip.py`

## Planned features

- `POST /relay/send` — send signed message to target chain
- `GET /relay/message/{id}` — fetch message status
- `POST /relay/verify` — verify AIP v0.3 envelope signature
- `GET /relay/chains` — list supported chains + status
- 15 chains: EVM (ETH, Polygon, BSC, Arb, Op, Base, Avax), Solana, Cosmos, Aptos, Sui, Near, Stellar, Kaspa, TON

## Stack

- Backend: Python 3.12 + FastAPI, port 8009
- Domain: relay.maxiaworld.app
