import pytest
import os
import tempfile
import chromadb
from chromadb.utils import embedding_functions
from unittest.mock import patch, MagicMock


def test_chunk_text_basic():
    """Test that chunk_text splits text into correct-sized chunks with overlap."""
    from backend.ingest_pdfs import chunk_text

    text = "A" * 1000
    chunks = chunk_text(text, chunk_size=400, overlap=50)

    assert len(chunks) >= 3
    assert all(len(c) <= 400 for c in chunks)
    # Check overlap: end of chunk N should overlap with start of chunk N+1
    assert chunks[0][-50:] == chunks[1][:50]


def test_chunk_text_short():
    """Short text should return a single chunk."""
    from backend.ingest_pdfs import chunk_text

    chunks = chunk_text("Hello world", chunk_size=400, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_chunk_text_empty():
    """Empty text should return empty list."""
    from backend.ingest_pdfs import chunk_text

    chunks = chunk_text("", chunk_size=400, overlap=50)
    assert chunks == []


def test_chunk_text_exact_boundary():
    """Text exactly at chunk_size should return a single chunk."""
    from backend.ingest_pdfs import chunk_text

    text = "B" * 400
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_find_all_pdfs():
    """find_all_pdfs should return PDF files recursively."""
    from backend.ingest_pdfs import find_all_pdfs

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        os.makedirs(os.path.join(tmpdir, "sub"), exist_ok=True)
        open(os.path.join(tmpdir, "test1.pdf"), "w").close()
        open(os.path.join(tmpdir, "sub", "test2.pdf"), "w").close()
        open(os.path.join(tmpdir, "not_a_pdf.txt"), "w").close()

        pdfs = find_all_pdfs(tmpdir)
        assert len(pdfs) == 2
        assert all(p.endswith(".pdf") for p in pdfs)
