"""
One-time PDF ingestion pipeline.
Reads PDFs from data/ directory, chunks text, embeds with SentenceTransformers,
and stores in persistent ChromaDB.

Usage:
    uv run python -m backend.ingest_pdfs
"""

import os
import glob
import pdfplumber
import chromadb
from chromadb.utils import embedding_functions
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_DB_PATH = os.path.join(DATA_DIR, "chroma_db")
COLLECTION_NAME = "medical_knowledge"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Split text into chunks of roughly `chunk_size` characters with `overlap`."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text from each page of a PDF. Returns list of {page, text}."""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    pages.append({"page": i + 1, "text": page_text.strip()})
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
    return pages


def find_all_pdfs(root_dir: str) -> list[str]:
    """Recursively find all PDF files under root_dir."""
    return glob.glob(os.path.join(root_dir, "**", "*.pdf"), recursive=True)


def ingest(data_dir: str = DATA_DIR, chroma_path: str = CHROMA_DB_PATH):
    """Main ingestion function. Extracts, chunks, embeds, and stores PDF content."""
    logger.info(f"Starting PDF ingestion from: {data_dir}")
    logger.info(f"ChromaDB persistence path: {chroma_path}")

    # Initialize persistent ChromaDB
    client = chromadb.PersistentClient(path=chroma_path)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    # Delete existing collection if it exists, then create fresh
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=ef
    )

    pdf_files = find_all_pdfs(data_dir)
    logger.info(f"Found {len(pdf_files)} PDF files")

    total_chunks = 0

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        logger.info(f"Processing: {filename}")

        pages = extract_text_from_pdf(pdf_path)
        if not pages:
            logger.warning(f"No text extracted from {filename}, skipping.")
            continue

        for page_data in pages:
            chunks = chunk_text(page_data["text"], chunk_size=400, overlap=50)
            for j, chunk in enumerate(chunks):
                doc_id = f"{filename}_p{page_data['page']}_c{j}"
                collection.add(
                    documents=[chunk],
                    metadatas=[{
                        "source": filename,
                        "page": page_data["page"],
                    }],
                    ids=[doc_id],
                )
                total_chunks += 1

    logger.info(f"Ingestion complete. {len(pdf_files)} PDFs -> {total_chunks} chunks stored.")
    return {"pdfs_processed": len(pdf_files), "chunks_stored": total_chunks}


if __name__ == "__main__":
    result = ingest()
    print(f"\nDone! Processed {result['pdfs_processed']} PDFs, stored {result['chunks_stored']} chunks.")
