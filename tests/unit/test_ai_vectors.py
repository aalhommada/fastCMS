"""Tests for the AI Vectors plugin — vector store and similarity search."""

import math
import os
import sys
import struct
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.conftest_ai import load_all_ai_plugins

load_all_ai_plugins()

from fastcms_plugin.ai_vectors.store import (
    VectorStore,
    VectorResult,
    _cosine_batch,
    _serialize_embedding,
    _deserialize_embedding,
)


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_roundtrip(self):
        original = [0.1, 0.2, 0.3, 0.4, 0.5]
        blob = _serialize_embedding(original)
        restored = _deserialize_embedding(blob)
        assert len(restored) == len(original)
        for a, b in zip(original, restored):
            assert abs(a - b) < 1e-6

    def test_empty(self):
        blob = _serialize_embedding([])
        restored = _deserialize_embedding(blob)
        assert restored == []

    def test_blob_size(self):
        emb = [1.0] * 1536  # OpenAI text-embedding-3-small dimension
        blob = _serialize_embedding(emb)
        assert len(blob) == 1536 * 4  # 4 bytes per float32


# ---------------------------------------------------------------------------
# Cosine similarity tests
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        q = [1.0, 0.0, 0.0]
        scores = _cosine_batch(q, [[1.0, 0.0, 0.0]])
        assert abs(scores[0] - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        q = [1.0, 0.0, 0.0]
        scores = _cosine_batch(q, [[0.0, 1.0, 0.0]])
        assert abs(scores[0]) < 1e-6

    def test_opposite_vectors(self):
        q = [1.0, 0.0]
        scores = _cosine_batch(q, [[-1.0, 0.0]])
        assert scores[0] < -0.99

    def test_batch(self):
        q = [1.0, 0.0, 0.0]
        vecs = [
            [1.0, 0.0, 0.0],   # identical
            [0.0, 1.0, 0.0],   # orthogonal
            [0.707, 0.707, 0.0],  # 45 degrees
        ]
        scores = _cosine_batch(q, vecs)
        assert abs(scores[0] - 1.0) < 1e-4
        assert abs(scores[1]) < 1e-4
        assert abs(scores[2] - 0.707) < 0.01

    def test_zero_query(self):
        q = [0.0, 0.0, 0.0]
        scores = _cosine_batch(q, [[1.0, 0.0, 0.0]])
        assert scores[0] == 0.0


# ---------------------------------------------------------------------------
# Vector store tests (using temp SQLite DB)
# ---------------------------------------------------------------------------

class TestVectorStore:
    @pytest.fixture
    def store(self, tmp_path):
        db_path = tmp_path / "test_vectors.db"
        return VectorStore(db_path=db_path)

    @pytest.mark.asyncio
    async def test_upsert_and_search(self, store):
        # Insert some vectors
        await store.upsert("articles", "rec1", "content", [1.0, 0.0, 0.0], "Hello world")
        await store.upsert("articles", "rec2", "content", [0.0, 1.0, 0.0], "Goodbye world")
        await store.upsert("articles", "rec3", "content", [0.9, 0.1, 0.0], "Similar to hello")

        # Search for vectors similar to [1.0, 0.0, 0.0]
        results = await store.search("articles", [1.0, 0.0, 0.0], limit=3)
        assert len(results) == 3
        assert results[0].record_id == "rec1"  # Most similar
        assert results[0].score > 0.99
        assert results[1].record_id == "rec3"  # Second most similar
        assert results[2].record_id == "rec2"  # Least similar

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self, store):
        await store.upsert("col", "r1", "f", [1.0, 0.0], "original")
        await store.upsert("col", "r1", "f", [0.0, 1.0], "updated")

        results = await store.search("col", [0.0, 1.0], limit=1)
        assert len(results) == 1
        assert results[0].text_content == "updated"

    @pytest.mark.asyncio
    async def test_search_empty_collection(self, store):
        results = await store.search("nonexistent", [1.0, 0.0], limit=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_threshold(self, store):
        await store.upsert("col", "r1", "f", [1.0, 0.0, 0.0], "match")
        await store.upsert("col", "r2", "f", [0.0, 1.0, 0.0], "no match")

        results = await store.search("col", [1.0, 0.0, 0.0], threshold=0.5)
        assert len(results) == 1
        assert results[0].record_id == "r1"

    @pytest.mark.asyncio
    async def test_delete_by_collection(self, store):
        await store.upsert("col1", "r1", "f", [1.0, 0.0], "a")
        await store.upsert("col1", "r2", "f", [0.0, 1.0], "b")
        await store.upsert("col2", "r3", "f", [1.0, 1.0], "c")

        deleted = await store.delete_by_collection("col1")
        assert deleted == 2

        # col2 should still be there
        results = await store.search("col2", [1.0, 1.0], limit=5)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_delete_by_record(self, store):
        await store.upsert("col", "r1", "f", [1.0, 0.0], "a")
        await store.upsert("col", "r2", "f", [0.0, 1.0], "b")

        deleted = await store.delete_by_record("col", "r1")
        assert deleted == 1

        results = await store.search("col", [1.0, 0.0], limit=5)
        assert len(results) == 1
        assert results[0].record_id == "r2"

    @pytest.mark.asyncio
    async def test_metadata(self, store):
        await store.upsert(
            "col", "r1", "f", [1.0, 0.0],
            "text", metadata={"source": "test.pdf", "page": 1}
        )
        results = await store.search("col", [1.0, 0.0], limit=1)
        assert results[0].metadata == {"source": "test.pdf", "page": 1}

    @pytest.mark.asyncio
    async def test_stats(self, store):
        await store.upsert("col1", "r1", "f", [1.0, 0.0], "a")
        await store.upsert("col1", "r2", "f", [0.0, 1.0], "b")
        await store.upsert("col2", "r3", "f", [1.0, 1.0], "c")

        stats = await store.stats()
        assert stats["total_embeddings"] == 3
        assert stats["collections"]["col1"] == 2
        assert stats["collections"]["col2"] == 1

    @pytest.mark.asyncio
    async def test_search_limit(self, store):
        for i in range(10):
            await store.upsert("col", f"r{i}", "f", [float(i % 3), float(i % 5)], f"text {i}")

        results = await store.search("col", [1.0, 0.0], limit=3)
        assert len(results) == 3
