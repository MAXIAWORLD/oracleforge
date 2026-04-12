"""Shared pytest fixtures for LLMForge backend tests."""

from __future__ import annotations

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEBUG", "true")
