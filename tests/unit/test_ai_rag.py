"""Tests for the AI RAG plugin — chunker and pipeline."""

import sys
from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.conftest_ai import load_all_ai_plugins

load_all_ai_plugins()

from fastcms_plugin.ai_rag.chunker import chunk_text, Chunk
from fastcms_plugin.ai_core.providers import CompletionResponse, EmbeddingResponse
from fastcms_plugin.ai_vectors.store import VectorStore, VectorResult

# Force-import pipeline submodule so it's in sys.modules
from fastcms_plugin.ai_rag import pipeline as _pipeline_mod


# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------

class TestChunker:
    def test_basic_chunking(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunk_text(text, chunk_size=40, chunk_overlap=0)
        assert len(chunks) >= 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_empty_text(self):
        chunks = chunk_text("", chunk_size=100)
        assert chunks == []

    def test_whitespace_only(self):
        chunks = chunk_text("   \n\n  ", chunk_size=100)
        assert chunks == []

    def test_single_sentence(self):
        text = "This is a single sentence."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_ids_unique(self):
        text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."
        chunks = chunk_text(text, chunk_size=20, chunk_overlap=0)
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_indices(self):
        text = "Alpha. Beta. Gamma. Delta. Epsilon."
        chunks = chunk_text(text, chunk_size=20, chunk_overlap=0)
        indices = [c.index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_source_in_metadata(self):
        text = "Hello world. This is a test."
        chunks = chunk_text(text, chunk_size=1000, source="test.pdf")
        assert chunks[0].metadata["source"] == "test.pdf"

    def test_overlap_preserves_context(self):
        text = "A. B. C. D. E. F. G. H. I. J."
        chunks_no_overlap = chunk_text(text, chunk_size=10, chunk_overlap=0)
        chunks_with_overlap = chunk_text(text, chunk_size=10, chunk_overlap=5)
        assert len(chunks_with_overlap) >= len(chunks_no_overlap)

    def test_long_sentence_split(self):
        text = " ".join(["word"] * 200)
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=0)
        assert len(chunks) >= 2

    def test_realistic_text(self):
        text = (
            "FastCMS is a Backend-as-a-Service built with FastAPI. "
            "It provides authentication, collections, file storage, and real-time features. "
            "The plugin system allows extending functionality with custom code. "
            "AI features are available through optional plugins."
        )
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        combined = " ".join(c.text for c in chunks)
        for word in ["FastCMS", "authentication", "plugin", "AI"]:
            assert word in combined

    def test_chunk_size_respected(self):
        text = "Short. Also short. And this. Plus that. More here."
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=0)
        for chunk in chunks:
            assert len(chunk.text) < 60


# ---------------------------------------------------------------------------
# Pipeline tests (mocked) — patches target source modules
# ---------------------------------------------------------------------------

class TestPipeline:
    @pytest.mark.asyncio
    async def test_ingest_document(self):
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                embeddings=[[0.1, 0.2, 0.3]] * 5,
                model="test-model",
                usage={},
            )
        )

        mock_store = AsyncMock(spec=VectorStore)
        mock_store.upsert = AsyncMock(return_value="emb-id")

        with (
            patch(
                "fastcms_plugin.ai_core.providers.get_embed_provider",
                return_value=mock_provider,
            ),
            patch(
                "fastcms_plugin.ai_vectors.store.VectorStore",
                return_value=mock_store,
            ),
        ):
            result = await _pipeline_mod.ingest_document(
                collection="docs",
                text="First paragraph. Second paragraph. Third paragraph.",
                source="readme.md",
                chunk_size=30,
                chunk_overlap=0,
            )
            assert result.collection == "docs"
            assert result.source == "readme.md"
            assert result.chunks > 0
            assert mock_store.upsert.call_count == result.chunks

    @pytest.mark.asyncio
    async def test_ask_question(self):
        mock_embed_provider = AsyncMock()
        mock_embed_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                embeddings=[[0.1, 0.2, 0.3]], model="test", usage={}
            )
        )

        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=CompletionResponse(
                content="The answer is 42.", model="gpt-4o", usage={}
            )
        )

        mock_store = AsyncMock(spec=VectorStore)
        mock_store.search = AsyncMock(
            return_value=[
                VectorResult(
                    id="v1",
                    collection_name="docs",
                    record_id="doc1:0",
                    field_name="chunk",
                    text_content="The meaning of life is 42.",
                    score=0.95,
                    metadata={"source": "guide.pdf"},
                )
            ]
        )

        with (
            patch(
                "fastcms_plugin.ai_core.providers.get_embed_provider",
                return_value=mock_embed_provider,
            ),
            patch(
                "fastcms_plugin.ai_core.providers.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "fastcms_plugin.ai_vectors.store.VectorStore",
                return_value=mock_store,
            ),
        ):
            result = await _pipeline_mod.ask_question(
                collection="docs",
                question="What is the meaning of life?",
            )
            assert "42" in result.answer
            assert len(result.sources) == 1
            assert result.sources[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_ask_no_results(self):
        mock_embed_provider = AsyncMock()
        mock_embed_provider.embed = AsyncMock(
            return_value=EmbeddingResponse(
                embeddings=[[0.1, 0.2]], model="test", usage={}
            )
        )

        mock_store = AsyncMock(spec=VectorStore)
        mock_store.search = AsyncMock(return_value=[])

        with (
            patch(
                "fastcms_plugin.ai_core.providers.get_embed_provider",
                return_value=mock_embed_provider,
            ),
            patch(
                "fastcms_plugin.ai_vectors.store.VectorStore",
                return_value=mock_store,
            ),
        ):
            result = await _pipeline_mod.ask_question(
                collection="docs", question="Unknown topic"
            )
            assert "couldn't find" in result.answer.lower()
            assert result.sources == []
