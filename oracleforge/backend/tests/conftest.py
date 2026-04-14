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
