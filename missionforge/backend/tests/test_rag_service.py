"""TDD tests for services/rag_service.py — Hybrid RAG retrieval."""

from __future__ import annotations

import os
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
def _prefix() -> str:
    return f"t{uuid.uuid4().hex[:6]}"


@pytest.fixture
def memory(chroma_client, _prefix):
    from services.memory import VectorMemory
    return VectorMemory(client=chroma_client, prefix=_prefix)


@pytest.fixture
def rag(chroma_client, memory, _prefix):
    from services.rag_service import RagService
    return RagService(chroma_client=chroma_client, memory=memory, prefix=_prefix)


@pytest.fixture
def sample_doc(tmp_path) -> str:
    """Create a sample text file for ingestion."""
    doc = tmp_path / "sample.txt"
    doc.write_text(
        "MissionForge is an AI agent framework. "
        "It supports YAML-based mission definitions with automatic scheduling. "
        "The LLM router provides multi-provider support with automatic fallback. "
        "RAG enables knowledge-grounded responses using ChromaDB vector search. "
        "Missions can include steps like rag_retrieve, llm_call, webhook, and memory_store. "
        "The dashboard provides real-time observability including token usage, cost tracking, "
        "and P50/P95 latency metrics per LLM tier.",
        encoding="utf-8",
    )
    return str(doc)


class TestIngestDocs:
    """RagService.ingest_docs() loads documents into ChromaDB."""

    def test_ingest_single_file(self, rag, sample_doc) -> None:
        result = rag.ingest_docs([(sample_doc, "sample")])
        assert result["chunks_added"] > 0
        assert result["files"] == 1
        assert result["elapsed_s"] >= 0

    def test_ingest_idempotent(self, rag, sample_doc) -> None:
        """Re-ingesting the same file should add 0 new chunks."""
        rag.ingest_docs([(sample_doc, "sample")])
        result = rag.ingest_docs([(sample_doc, "sample")])
        assert result["chunks_added"] == 0
        assert result["skipped"] > 0

    def test_ingest_missing_file(self, rag) -> None:
        result = rag.ingest_docs([("/nonexistent/path.txt", "missing")])
        assert result["files"] == 0
        assert len(result["errors"]) > 0

    def test_ingest_force_reindex(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        result = rag.ingest_docs([(sample_doc, "sample")], force=True)
        assert result["chunks_added"] > 0


class TestHybridRetrieve:
    """RagService.hybrid_retrieve() returns relevant chunks."""

    def test_retrieve_returns_results(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        results = rag.hybrid_retrieve("YAML mission definitions")
        assert len(results) >= 1
        assert "score" in results[0]
        assert "text" in results[0]

    def test_retrieve_empty_query(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        results = rag.hybrid_retrieve("")
        assert results == []

    def test_retrieve_no_data(self, rag) -> None:
        results = rag.hybrid_retrieve("anything")
        assert results == []

    def test_keyword_overlay_for_acronyms(self, rag, tmp_path) -> None:
        """Short acronyms should be found via keyword overlay."""
        doc = tmp_path / "acronyms.txt"
        doc.write_text(
            "The RAG system uses ChromaDB for vector storage. "
            "SSE is used for live log streaming. "
            "JWT tokens handle authentication. "
            "The CLI supports init, start, stop, and status commands.",
            encoding="utf-8",
        )
        rag.ingest_docs([(str(doc), "acronyms")])
        results = rag.hybrid_retrieve("SSE streaming")
        assert len(results) >= 1
        # At least one result should mention SSE
        texts = " ".join(r["text"] for r in results)
        assert "SSE" in texts


class TestBuildRagContext:
    """RagService.build_rag_context() formats retrieval for LLM prompts."""

    def test_builds_context_string(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        context = rag.build_rag_context("mission framework")
        assert isinstance(context, str)
        assert len(context) > 0

    def test_respects_max_chars(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        context = rag.build_rag_context("mission framework", max_chars=100)
        assert len(context) <= 150  # Some slack for formatting

    def test_empty_when_no_data(self, rag) -> None:
        context = rag.build_rag_context("anything")
        assert context == ""

    def test_header_included(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        context = rag.build_rag_context("mission", header="## Knowledge Base")
        assert context.startswith("## Knowledge Base")


class TestStats:
    """RagService.stats() returns collection info."""

    def test_empty_stats(self, rag) -> None:
        stats = rag.stats()
        assert stats["chunks"] == 0

    def test_stats_after_ingest(self, rag, sample_doc) -> None:
        rag.ingest_docs([(sample_doc, "sample")])
        stats = rag.stats()
        assert stats["chunks"] > 0
        assert stats["ok"] is True
