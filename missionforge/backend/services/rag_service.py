"""MissionForge — Hybrid RAG service (vector + keyword overlay).

Extracted from MAXIA V12 local_ceo/rag_knowledge.py and generalised:
- Class-based (no module globals, no singleton)
- ChromaDB client injected (shares client with VectorMemory)
- Configurable collection names via prefix
- No hardcoded MAXIA paths — sources passed via API
- Fail-soft: returns safe defaults when ChromaDB unavailable

Retrieval strategy:
  1. Vector search (ChromaDB cosine similarity) for top-k*2 candidates
  2. Keyword overlay for rare tokens/acronyms that embeddings miss
  3. Dedup by text prefix, keep highest score
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from collections.abc import Iterable
from typing import Any

from services.memory import VectorMemory

logger = logging.getLogger(__name__)

# Chunking parameters (validated by MAXIA V12 POC: 300/40 optimal)
CHUNK_SIZE = 300
CHUNK_OVERLAP = 40
MIN_CHUNK_CHARS = 20

# Stopwords for keyword extraction
_STOPWORDS = frozenset({
    "what", "which", "does", "have", "support", "the", "you",
    "for", "your", "are", "there", "how", "why", "when", "where", "who",
    "can", "will", "should", "would", "could", "is", "am", "was", "were",
    "do", "did", "has", "had", "a", "an", "in", "on", "of", "to", "from",
    "with", "about", "and", "or", "but", "not", "all", "any", "some",
})

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


class RagService:
    """Hybrid RAG: ChromaDB vector search + keyword overlay."""

    def __init__(
        self,
        chroma_client: Any,
        memory: VectorMemory,
        prefix: str = "mf",
    ) -> None:
        self._client = chroma_client
        self._memory = memory
        self._prefix = prefix
        self._coll: Any = None
        self._ok = chroma_client is not None
        self._chunk_cache: list[tuple[str, str]] = []

    @property
    def _collection_name(self) -> str:
        return f"{self._prefix}_knowledge_docs"

    def _get_collection(self) -> Any | None:
        """Get or create the knowledge_docs collection."""
        if self._coll is not None:
            return self._coll
        if not self._ok:
            return None
        try:
            self._coll = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            return self._coll
        except Exception as e:
            logger.warning("[rag] collection init failed: %s", e)
            return None

    # ── Chunking ─────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(
        text: str,
        size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> list[str]:
        """Split text into overlapping chunks, preferring whitespace boundaries."""
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            end = min(i + size, n)
            if end < n:
                sp = text.rfind(" ", i + size // 2, end)
                if sp > 0:
                    end = sp
            piece = text[i:end].strip()
            if len(piece) >= MIN_CHUNK_CHARS:
                out.append(piece)
            if end >= n:
                break
            i = end - overlap
        return out

    @staticmethod
    def _doc_id(tag: str, text: str) -> str:
        """Deterministic ID — re-ingesting same text is a no-op."""
        h = hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:10]
        return f"{tag}_{h}"

    # ── Ingestion ────────────────────────────────────────────────

    def ingest_docs(
        self,
        sources: Iterable[tuple[str, str]],
        force: bool = False,
    ) -> dict:
        """Ingest documents into the knowledge collection.

        Args:
            sources: Iterable of (file_path, tag) pairs.
            force: If True, delete existing chunks for each tag first.

        Returns:
            {"chunks_added", "files", "skipped", "elapsed_s", "errors"}
        """
        coll = self._get_collection()
        if coll is None:
            return {
                "chunks_added": 0, "files": 0, "skipped": 0,
                "elapsed_s": 0.0, "errors": ["collection unavailable"],
            }

        sources_list = list(sources)
        t0 = time.time()
        added = 0
        files_ok = 0
        skipped = 0
        errors: list[str] = []

        existing_ids: set[str] = set()
        if not force:
            try:
                all_ids = coll.get(include=[])
                existing_ids = set(all_ids.get("ids") or [])
            except Exception:
                pass

        for path, tag in sources_list:
            # Path traversal protection: resolve and validate
            try:
                real_path = os.path.realpath(path)
            except (ValueError, OSError):
                errors.append(f"invalid path: {path}")
                continue
            if not os.path.exists(real_path):
                errors.append(f"missing: {path}")
                continue
            try:
                with open(real_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError as e:
                errors.append(f"read {path}: {e}")
                continue

            if force:
                try:
                    coll.delete(where={"source": tag})
                except Exception as e:
                    logger.warning("[rag] delete(tag=%s) failed: %s", tag, e)

            pieces = self._chunk_text(text)
            if not pieces:
                continue

            ids: list[str] = []
            docs: list[str] = []
            metas: list[dict] = []
            for idx, piece in enumerate(pieces):
                did = self._doc_id(tag, piece)
                if did in existing_ids:
                    skipped += 1
                    continue
                ids.append(did)
                docs.append(piece)
                metas.append({
                    "source": tag,
                    "path": path,
                    "idx": idx,
                    "indexed_at": int(time.time()),
                })
                existing_ids.add(did)

            if ids:
                try:
                    coll.add(documents=docs, metadatas=metas, ids=ids)
                    added += len(ids)
                except Exception as e:
                    errors.append(f"add {tag}: {e}")
                    continue
            files_ok += 1

        self._refresh_chunk_cache()

        elapsed = time.time() - t0
        return {
            "chunks_added": added,
            "files": files_ok,
            "skipped": skipped,
            "elapsed_s": round(elapsed, 2),
            "errors": errors,
        }

    # ── Chunk cache (for keyword overlay) ────────────────────────

    def _refresh_chunk_cache(self) -> None:
        """Rebuild the in-memory chunk cache from ChromaDB."""
        coll = self._get_collection()
        if coll is None:
            self._chunk_cache = []
            return
        try:
            all_data = coll.get(include=["documents", "metadatas"])
            docs = all_data.get("documents") or []
            metas = all_data.get("metadatas") or []
            self._chunk_cache = [
                (str(d), str((m or {}).get("source", "")))
                for d, m in zip(docs, metas)
            ]
        except Exception as e:
            logger.warning("[rag] chunk cache refresh failed: %s", e)
            self._chunk_cache = []

    # ── Keyword extraction ───────────────────────────────────────

    @staticmethod
    def _extract_query_keywords(query: str) -> list[str]:
        """Extract short/rare tokens for keyword overlay (acronyms, IDs)."""
        words = [w.lower() for w in _TOKEN_RE.findall(query)]
        seen: set[str] = set()
        out: list[str] = []
        for w in words:
            if w in _STOPWORDS or w in seen:
                continue
            if len(w) <= 6 or any(c.isdigit() for c in w):
                seen.add(w)
                out.append(w)
        return out

    # ── Retrieval ────────────────────────────────────────────────

    def hybrid_retrieve(self, query: str, k: int = 6) -> list[dict]:
        """Vector search + keyword overlay, deduplicated and sorted.

        Returns list of {"text", "source", "score"}.
        """
        if not isinstance(query, str) or not query.strip():
            return []
        coll = self._get_collection()
        if coll is None:
            return []

        # 1. Vector search (top k*2 for dedup headroom)
        vec_results: list[tuple[str, str, float]] = []
        try:
            count = coll.count()
            n = min(k * 2, max(1, count))
            if n > 0 and count > 0:
                r = coll.query(query_texts=[query], n_results=n)
                docs = (r.get("documents") or [[]])[0]
                dists = (r.get("distances") or [[]])[0]
                metas = (r.get("metadatas") or [[]])[0]
                for d, m, dist in zip(docs, metas, dists):
                    source = str((m or {}).get("source", ""))
                    score = max(0.0, 1.0 - float(dist))
                    vec_results.append((str(d), source, score))
        except Exception as e:
            logger.warning("[rag] vector query failed: %s", e)

        # 2. Keyword overlay for rare tokens
        if not self._chunk_cache:
            self._refresh_chunk_cache()
        rare_tokens = self._extract_query_keywords(query)
        kw_results: list[tuple[str, str, float]] = []
        if rare_tokens and self._chunk_cache:
            for text, source in self._chunk_cache:
                tl = text.lower()
                hits = sum(1 for tok in rare_tokens if tok in tl)
                if hits > 0:
                    kscore = min(0.95, 0.50 + 0.15 * hits)
                    kw_results.append((text, source, kscore))

        # 3. Dedup by chunk prefix, keep max score
        merged: dict[str, tuple[str, str, float]] = {}
        for text, source, score in vec_results + kw_results:
            key = text[:80]
            prev = merged.get(key)
            if prev is None or prev[2] < score:
                merged[key] = (text, source, score)

        sorted_hits = sorted(merged.values(), key=lambda x: -x[2])[:k]
        return [
            {"text": t, "source": s, "score": round(sc, 3)}
            for t, s, sc in sorted_hits
        ]

    # ── Context builder ──────────────────────────────────────────

    def build_rag_context(
        self,
        query: str,
        max_chars: int = 2500,
        header: str | None = None,
    ) -> str:
        """Build a prompt-ready context block from retrieved chunks."""
        hits = self.hybrid_retrieve(query, k=6)
        if not hits:
            return ""

        parts: list[str] = []
        if header:
            parts.append(header.strip())
        used = sum(len(p) for p in parts)

        for h in hits:
            snippet = h["text"].strip()
            line = f"[{h['source']} | score={h['score']}] {snippet}"
            if used + len(line) + 2 > max_chars:
                break
            parts.append(line)
            used += len(line) + 2

        return "\n\n".join(parts)

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return collection size and cache info."""
        coll = self._get_collection()
        if coll is None:
            return {"ok": False, "chunks": 0, "cache": 0}
        try:
            return {
                "ok": True,
                "chunks": int(coll.count()),
                "cache": len(self._chunk_cache),
            }
        except Exception:
            return {"ok": False, "chunks": 0, "cache": 0}
