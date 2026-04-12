"""TDD tests for services/memory.py — VectorMemory ChromaDB wrapper."""

from __future__ import annotations

import uuid

import pytest

import chromadb
import chromadb.config


@pytest.fixture
def chroma_client(tmp_path) -> chromadb.ClientAPI:
    """PersistentClient in tmp dir — truly isolated per test."""
    return chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )


@pytest.fixture
def prefix() -> str:
    return f"t{uuid.uuid4().hex[:6]}"


@pytest.fixture
def memory(chroma_client, prefix):
    from services.memory import VectorMemory
    return VectorMemory(client=chroma_client, prefix=prefix)


class TestStore:
    """VectorMemory.store() persists text in ChromaDB."""

    def test_store_and_search(self, memory, prefix) -> None:
        memory.store(f"{prefix}_notes", "Python is a great programming language")
        results = memory.search("programming language", collection=f"{prefix}_notes")
        assert len(results) >= 1
        assert "Python" in results[0]["text"]

    def test_store_ignores_short_text(self, memory, prefix) -> None:
        memory.store(f"{prefix}_notes", "hi")  # < 5 chars, should be ignored
        results = memory.search("hi", collection=f"{prefix}_notes")
        assert len(results) == 0

    def test_store_with_metadata(self, memory, prefix) -> None:
        memory.store(f"{prefix}_notes", "FastAPI is blazing fast", {"topic": "web"})
        results = memory.search("fast web framework", collection=f"{prefix}_notes")
        assert len(results) >= 1
        assert results[0]["metadata"].get("topic") == "web"


class TestStoreTyped:
    """Typed store methods (store_action, store_decision, store_learning)."""

    def test_store_action(self, memory, prefix) -> None:
        memory.store_action("tweet", "@user", "Great AI insights today")
        results = memory.search("AI insights", collection=f"{prefix}_actions")
        assert len(results) >= 1

    def test_store_decision(self, memory, prefix) -> None:
        memory.store_decision("Decided to use FastAPI for all products")
        results = memory.search("FastAPI decision", collection=f"{prefix}_decisions")
        assert len(results) >= 1

    def test_store_learning(self, memory, prefix) -> None:
        memory.store_learning("Always validate user input", source="security audit")
        results = memory.search("validate input", collection=f"{prefix}_learnings")
        assert len(results) >= 1


class TestSearch:
    """VectorMemory.search() retrieves by semantic similarity."""

    def test_search_specific_collection(self, memory, prefix) -> None:
        coll = f"{prefix}_docs"
        memory.store(coll, "Machine learning is transforming industries")
        memory.store(coll, "Deep learning uses neural networks")
        results = memory.search("neural networks ML", collection=coll)
        assert len(results) >= 1

    def test_search_returns_score(self, memory, prefix) -> None:
        coll = f"{prefix}_notes"
        memory.store(coll, "ChromaDB is a vector database")
        results = memory.search("vector database", collection=coll)
        assert len(results) >= 1
        assert 0 <= results[0]["score"] <= 1.0

    def test_search_empty_collection(self, memory, prefix) -> None:
        results = memory.search("anything", collection=f"{prefix}_empty")
        assert results == []


class TestHasSimilar:
    """VectorMemory.has_similar() detects semantic duplicates."""

    def test_similar_action_detected(self, memory) -> None:
        memory.store_action("tweet", "@dev", "Solana DeFi yields are amazing")
        assert memory.has_similar("tweet", "DeFi yields on Solana") is True

    def test_dissimilar_not_detected(self, memory) -> None:
        memory.store_action("tweet", "@dev", "Solana DeFi yields are amazing")
        assert memory.has_similar("tweet", "quantum computing advances") is False

    def test_different_action_type_not_matched(self, memory) -> None:
        memory.store_action("tweet", "@dev", "Great AI discussion")
        assert memory.has_similar("reply", "Great AI discussion") is False


class TestStats:
    """VectorMemory.stats() returns collection counts."""

    def test_empty_stats(self, memory) -> None:
        stats = memory.stats()
        assert stats["total"] == 0

    def test_stats_after_typed_store(self, memory) -> None:
        memory.store_action("tweet", "@user", "Hello world from MissionForge")
        stats = memory.stats()
        assert stats["total"] >= 1
        assert "collections" in stats


class TestCollectionIsolation:
    """Collections are isolated from each other."""

    def test_different_collections_isolated(self, memory, prefix) -> None:
        memory.store(f"{prefix}_alpha", "Data only in alpha collection")
        results_alpha = memory.search("alpha data", collection=f"{prefix}_alpha")
        results_beta = memory.search("alpha data", collection=f"{prefix}_beta")
        assert len(results_alpha) >= 1
        assert len(results_beta) == 0
