import os
import chromadb
from chromadb.utils import embedding_functions
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "data", "chroma_db")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "medical_knowledge"

# Initialize persistent ChromaDB client
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME, embedding_function=sentence_transformer_ef
)


def query_rag_context(query: str, n_results: int = 3) -> str:
    """
    Query the ChromaDB collection for relevant guideline context.
    Returns top n_results as concatenated text.
    """
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        if results and "documents" in results and results["documents"]:
            context_pieces = results["documents"][0]
            return "\n\n".join(context_pieces)
        return ""
    except Exception as e:
        logger.error(f"Error querying ChromaDB: {e}")
        return ""
