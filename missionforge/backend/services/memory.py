"""MissionForge — Vector memory backed by ChromaDB.

Extracted from MAXIA V12 local_ceo/vector_memory_local.py and generalised:
- No singleton — ChromaDB client injected via __init__
- Collection names use configurable prefix (multi-tenant ready)
- No hardcoded paths
- Fail-soft: returns safe defaults if ChromaDB is unavailable
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class VectorMemory:
    """Semantic vector memory using ChromaDB collections."""

    def __init__(self, client: Any, prefix: str = "mf") -> None:
        self._client = client
        self._prefix = prefix
        self._collections: dict[str, Any] = {}
        self._ok = client is not None

    def _coll(self, name: str) -> Any | None:
        """Lazy-load or create a ChromaDB collection."""
        if not self._ok:
            return None
        if name not in self._collections:
            try:
                self._collections[name] = self._client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                logger.warning("[VectorMemory] collection '%s' init failed: %s", name, e)
                return None
        return self._collections[name]

    # ── Store ────────────────────────────────────────────────────

    def store(
        self, collection: str, text: str, metadata: dict | None = None
    ) -> None:
        """Store text with embedding in the specified collection."""
        if not self._ok or not text or len(text.strip()) < 5:
            return
        coll = self._coll(collection)
        if coll is None:
            return

        meta = {
            k: (v if isinstance(v, (str, int, float, bool)) else str(v))
            for k, v in (metadata or {}).items()
        }
        meta.setdefault("ts", int(time.time()))
        meta.setdefault("date", time.strftime("%Y-%m-%d %H:%M"))
        doc_id = f"{collection}_{int(time.time() * 1000)}_{hash(text) % 10000}"

        try:
            coll.add(documents=[text], metadatas=[meta], ids=[doc_id])
        except Exception as e:
            logger.warning("[VectorMemory] store error: %s", e)

    def store_action(
        self, action_type: str, target: str, content: str
    ) -> None:
        """Store an action (tweet, reply, comment, etc.)."""
        text = f"[{action_type}] {target}: {content}"
        self.store(f"{self._prefix}_actions", text, {
            "action": action_type,
            "target": target,
        })

    def store_decision(self, summary: str, context: str = "") -> None:
        """Store a strategic decision."""
        self.store(f"{self._prefix}_decisions", summary, {"context": context})

    def store_learning(self, rule: str, source: str = "") -> None:
        """Store a learned rule or insight."""
        self.store(f"{self._prefix}_learnings", rule, {"source": source})

    # ── Search ───────────────────────────────────────────────────

    def search(
        self, query: str, collection: str | None = None, n: int = 5
    ) -> list[dict]:
        """Semantic search across one or all collections.

        Returns list of {"text", "score", "collection", "metadata"}.
        """
        if not self._ok:
            return []

        colls = (
            [collection]
            if collection
            else [
                f"{self._prefix}_actions",
                f"{self._prefix}_decisions",
                f"{self._prefix}_learnings",
            ]
        )

        results: list[dict] = []
        for name in colls:
            coll = self._coll(name)
            if coll is None:
                continue
            try:
                count = coll.count()
                if count == 0:
                    continue
                r = coll.query(query_texts=[query], n_results=min(n, count))
                if r and r["documents"] and r["documents"][0]:
                    for i, doc in enumerate(r["documents"][0]):
                        dist = (
                            r["distances"][0][i]
                            if r.get("distances") and r["distances"][0]
                            else 0.0
                        )
                        meta = (
                            r["metadatas"][0][i]
                            if r.get("metadatas") and r["metadatas"][0]
                            else {}
                        )
                        results.append({
                            "text": doc,
                            "score": round(max(0.0, 1.0 - dist), 3),
                            "collection": name,
                            "metadata": meta,
                        })
            except Exception:
                pass

        results.sort(key=lambda x: -x["score"])
        return results[:n]

    def has_similar(
        self, action_type: str, content: str, threshold: float = 0.85
    ) -> bool:
        """Check if a semantically similar action already exists (dedup)."""
        if not self._ok:
            return False
        results = self.search(
            f"[{action_type}] {content}",
            collection=f"{self._prefix}_actions",
            n=3,
        )
        return any(
            r["score"] >= threshold
            and r.get("metadata", {}).get("action") == action_type
            for r in results
        )

    def search_context(self, query: str, n: int = 5) -> str:
        """Return search results formatted for LLM prompt injection."""
        results = self.search(query, n=n)
        if not results:
            return "(No relevant memories)"
        lines = []
        for r in results:
            pct = int(r["score"] * 100)
            date = r.get("metadata", {}).get("date", "")
            lines.append(f"[{pct}% | {r['collection']} | {date}] {r['text'][:200]}")
        return "\n".join(lines)

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return collection counts and total."""
        if not self._ok:
            return {"backend": "disabled", "total": 0}
        default_colls = [
            f"{self._prefix}_actions",
            f"{self._prefix}_decisions",
            f"{self._prefix}_learnings",
        ]
        counts: dict[str, int] = {}
        for name in default_colls:
            try:
                coll = self._coll(name)
                counts[name] = coll.count() if coll else 0
            except Exception:
                counts[name] = 0
        return {
            "backend": "chromadb",
            "collections": counts,
            "total": sum(counts.values()),
        }
