"""
Unit tests for RAG file extractors.
"""

import json
import pytest

from plugins.ai_rag.extractors import extract_text


class TestTextExtractor:
    """Tests for plain text extraction."""

    def test_txt_file(self):
        content = b"Hello world. This is a test document."
        result = extract_text(content, "test.txt")
        assert result == "Hello world. This is a test document."

    def test_text_extension(self):
        content = b"Some text content"
        result = extract_text(content, "notes.text")
        assert result == "Some text content"

    def test_log_extension(self):
        content = b"2024-01-01 INFO: Server started"
        result = extract_text(content, "app.log")
        assert result == "2024-01-01 INFO: Server started"

    def test_empty_text_file(self):
        result = extract_text(b"  \n  ", "empty.txt")
        assert result.strip() == ""


class TestMarkdownExtractor:
    """Tests for Markdown text extraction."""

    def test_strips_headers(self):
        content = b"# Title\n## Subtitle\nSome content here."
        result = extract_text(content, "doc.md")
        assert "Title" in result
        assert "Subtitle" in result
        assert "#" not in result

    def test_strips_bold_italic(self):
        content = b"This is **bold** and *italic* text."
        result = extract_text(content, "doc.md")
        assert "bold" in result
        assert "italic" in result
        assert "**" not in result
        assert "*italic*" not in result

    def test_converts_links(self):
        content = b"Visit [FastCMS](https://fastcms.dev) for more info."
        result = extract_text(content, "doc.md")
        assert "FastCMS" in result
        assert "[" not in result
        assert "https://fastcms.dev" not in result

    def test_removes_code_blocks(self):
        content = b"Before\n```python\nprint('hello')\n```\nAfter"
        result = extract_text(content, "doc.md")
        assert "Before" in result
        assert "After" in result
        assert "```" not in result

    def test_strips_list_markers(self):
        content = b"- Item one\n- Item two\n1. Numbered"
        result = extract_text(content, "doc.markdown")
        assert "Item one" in result
        assert "Item two" in result
        assert "Numbered" in result


class TestHTMLExtractor:
    """Tests for HTML text extraction."""

    def test_strips_tags(self):
        content = b"<html><body><h1>Title</h1><p>Paragraph text.</p></body></html>"
        result = extract_text(content, "page.html")
        assert "Title" in result
        assert "Paragraph text." in result
        assert "<" not in result

    def test_ignores_script_style(self):
        content = b"<p>Visible</p><script>alert('xss')</script><style>.cls{}</style><p>Also visible</p>"
        result = extract_text(content, "page.htm")
        assert "Visible" in result
        assert "Also visible" in result
        assert "alert" not in result
        assert ".cls" not in result

    def test_preserves_text_structure(self):
        content = b"<h1>Header</h1><p>First paragraph.</p><p>Second paragraph.</p>"
        result = extract_text(content, "doc.html")
        assert "Header" in result
        assert "First paragraph." in result
        assert "Second paragraph." in result


class TestCSVExtractor:
    """Tests for CSV text extraction."""

    def test_csv_to_text(self):
        content = b"name,age,city\nAlice,30,New York\nBob,25,London"
        result = extract_text(content, "data.csv")
        assert "name: Alice" in result
        assert "age: 30" in result
        assert "city: New York" in result
        assert "name: Bob" in result

    def test_empty_csv(self):
        content = b""
        result = extract_text(content, "empty.csv")
        assert result == ""


class TestJSONExtractor:
    """Tests for JSON text extraction."""

    def test_json_formatted(self):
        data = {"name": "FastCMS", "version": "1.0"}
        content = json.dumps(data).encode()
        result = extract_text(content, "config.json")
        assert "FastCMS" in result
        assert "1.0" in result


class TestUnsupportedFormats:
    """Tests for unsupported file types."""

    def test_unsupported_extension(self):
        with pytest.raises(ValueError, match="Unsupported file type: .docx"):
            extract_text(b"content", "file.docx")

    def test_unknown_extension(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(b"content", "file.xyz")


class TestPDFExtractor:
    """Tests for PDF extraction (requires PyPDF2)."""

    def test_pdf_without_pypdf2(self):
        """If PyPDF2 is not installed, should raise a helpful error."""
        try:
            import PyPDF2
            pytest.skip("PyPDF2 is installed, skipping missing-dependency test")
        except ImportError:
            with pytest.raises(ValueError, match="PyPDF2"):
                extract_text(b"%PDF-1.4 fake pdf", "doc.pdf")
