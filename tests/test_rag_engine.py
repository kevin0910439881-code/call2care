import pytest
from backend.rag_engine import query_rag_context


def test_query_rag_context_returns_guidelines():
    """Test that RAG retrieves medical guideline context."""
    result = query_rag_context("糖尿病", n_results=3)
    assert isinstance(result, str)
    assert len(result) > 0


def test_query_rag_context_returns_string():
    """Test that query always returns a string."""
    result = query_rag_context("random query that matches nothing specific")
    assert isinstance(result, str)
