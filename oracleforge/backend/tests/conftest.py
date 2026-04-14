"""Pytest fixtures for the MAXIA Oracle Phase 3 API tests.

Sets required environment variables BEFORE any project module is imported,
so `core.config`'s strict startup validation succeeds in-process.

Each test gets a fresh DB path via pytest's tmp_path fixture; we tear down
the module-level shared connection between test modules so nothing bleeds.
"""
from __future__ import annotations

import os

# Env vars MUST be set before `core.config` is imported.
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("API_KEY_PEPPER", "test-pepper-that-is-more-than-32-chars-long")
os.environ.setdefault("LOG_LEVEL", "WARNING")
# Phase 4: treasury address is set at session scope so the x402 middleware
# populates the 402 `accepts` list in both Phase 3 and Phase 4 test modules.
# In dev mode this var is optional; tests set it so the behavior is
# deterministic across runs.
os.environ.setdefault(
    "X402_TREASURY_ADDRESS_BASE",
    "0xb3C5AF291eeA9D11DE7178B28eaF443359900f41",
)
