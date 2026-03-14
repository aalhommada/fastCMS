"""
Unit tests for RAG file upload endpoint.

Tests the upload route handler with mocked pipeline to avoid needing
real AI providers or vector stores.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from plugins.ai_rag.routes import router


# Create a test app with just the RAG routes
test_app = FastAPI()
test_app.include_router(router, prefix="/rag")


@pytest.fixture
def client():
    return TestClient(test_app)


@pytest.fixture
def mock_pipeline():
    """Mock the RAG pipeline so we don't need real AI providers."""
    from plugins.ai_rag.pipeline import IngestResult

    mock_result = IngestResult(
        document_id="test-doc-123",
        chunks=5,
        collection="test-collection",
        source="test.txt",
    )

    with patch("plugins.ai_rag.routes.ingest_document", create=True):
        with patch("plugins.ai_rag.pipeline.ingest_document", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = mock_result
            yield mock_ingest


class TestUploadEndpoint:
    """Tests for POST /rag/upload."""

    def test_upload_txt_file(self, client, mock_pipeline):
        resp = client.post(
            "/rag/upload",
            files={"file": ("readme.txt", b"This is a test document with some content.", "text/plain")},
            data={"collection": "test-collection"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == "test-doc-123"
        assert data["chunks"] == 5
        assert data["collection"] == "test-collection"

    def test_upload_md_file(self, client, mock_pipeline):
        md_content = b"# Title\n\nThis is **bold** text.\n\n- Item 1\n- Item 2"
        resp = client.post(
            "/rag/upload",
            files={"file": ("doc.md", md_content, "text/markdown")},
            data={"collection": "docs"},
        )
        assert resp.status_code == 200
        # Verify markdown was stripped before ingestion
        call_kwargs = mock_pipeline.call_args[1]
        text = call_kwargs["text"]
        assert "Title" in text
        assert "bold" in text
        assert "**" not in text

    def test_upload_html_file(self, client, mock_pipeline):
        html = b"<html><body><h1>Hello</h1><p>World</p><script>alert(1)</script></body></html>"
        resp = client.post(
            "/rag/upload",
            files={"file": ("page.html", html, "text/html")},
            data={"collection": "web"},
        )
        assert resp.status_code == 200
        call_kwargs = mock_pipeline.call_args[1]
        text = call_kwargs["text"]
        assert "Hello" in text
        assert "World" in text
        assert "<" not in text
        assert "alert" not in text

    def test_upload_csv_file(self, client, mock_pipeline):
        csv_data = b"name,role\nAlice,Admin\nBob,User"
        resp = client.post(
            "/rag/upload",
            files={"file": ("users.csv", csv_data, "text/csv")},
            data={"collection": "data"},
        )
        assert resp.status_code == 200
        call_kwargs = mock_pipeline.call_args[1]
        assert "name: Alice" in call_kwargs["text"]

    def test_upload_empty_file(self, client):
        resp = client.post(
            "/rag/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"collection": "test"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_upload_unsupported_format(self, client):
        resp = client.post(
            "/rag/upload",
            files={"file": ("doc.docx", b"fake content", "application/octet-stream")},
            data={"collection": "test"},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_upload_custom_chunk_size(self, client, mock_pipeline):
        resp = client.post(
            "/rag/upload",
            files={"file": ("test.txt", b"Some document content here.", "text/plain")},
            data={"collection": "test", "chunk_size": "1000", "chunk_overlap": "100"},
        )
        assert resp.status_code == 200
        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["chunk_size"] == 1000
        assert call_kwargs["chunk_overlap"] == 100

    def test_upload_whitespace_only_file(self, client):
        resp = client.post(
            "/rag/upload",
            files={"file": ("blank.txt", b"   \n\n  \t  ", "text/plain")},
            data={"collection": "test"},
        )
        assert resp.status_code == 400
        assert "No text" in resp.json()["detail"]

    def test_upload_default_collection(self, client, mock_pipeline):
        """Default collection should be 'knowledge-base'."""
        resp = client.post(
            "/rag/upload",
            files={"file": ("test.txt", b"Content here.", "text/plain")},
        )
        assert resp.status_code == 200
        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["collection"] == "knowledge-base"
