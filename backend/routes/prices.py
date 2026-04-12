"""OracleForge — Price API routes.

Endpoints:
  GET /api/price/{symbol}       — single price with confidence
  POST /api/prices/batch        — multi-symbol batch
  GET /api/sources              — source health status
  GET /api/cache/stats          — cache statistics
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.models import PriceResponse, BatchPriceResponse

router = APIRouter(prefix="/api", tags=["prices"])


def _get_engine(request: Request):
    engine = getattr(request.app.state, "price_engine", None)
    if engine is None:
        raise HTTPException(503, "Price engine not initialised")
    return engine


class BatchRequest(BaseModel):
    symbols: list[str]


@router.get("/price/{symbol}", response_model=PriceResponse)
async def get_price(symbol: str, request: Request) -> PriceResponse:
    """Get price with confidence score for a single symbol."""
    engine = _get_engine(request)
    result = await engine.get_price(symbol)
    if result.price_usd == 0:
        raise HTTPException(404, f"No price data for {symbol}")
    return PriceResponse(
        symbol=result.symbol,
        price_usd=result.price_usd,
        confidence=result.confidence,
        sources_used=result.sources_used,
        sources_available=result.sources_available,
        latency_ms=result.latency_ms,
        cached=result.cached,
    )


@router.post("/prices/batch", response_model=BatchPriceResponse)
async def batch_prices(req: BatchRequest, request: Request) -> BatchPriceResponse:
    """Get prices for multiple symbols in parallel."""
    if not req.symbols:
        raise HTTPException(400, "symbols list cannot be empty")
    if len(req.symbols) > 50:
        raise HTTPException(400, "Maximum 50 symbols per batch")
    engine = _get_engine(request)
    results = await engine.get_batch_prices(req.symbols)
    total_ms = max((r.latency_ms for r in results), default=0)
    return BatchPriceResponse(
        prices=[
            PriceResponse(
                symbol=r.symbol,
                price_usd=r.price_usd,
                confidence=r.confidence,
                sources_used=r.sources_used,
                sources_available=r.sources_available,
                latency_ms=r.latency_ms,
                cached=r.cached,
            )
            for r in results
        ],
        total_latency_ms=total_ms,
    )


@router.get("/sources")
async def sources(request: Request) -> dict:
    """Get health status of all price sources."""
    engine = _get_engine(request)
    return {"sources": engine.get_source_statuses()}


@router.get("/cache/stats")
async def cache_stats(request: Request) -> dict:
    engine = _get_engine(request)
    return engine.cache_stats()
