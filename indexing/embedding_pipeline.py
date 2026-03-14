"""Generate embeddings for code symbols."""

import logging
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """An embedding result for a symbol."""
    symbol_id: str
    embedding: list[float]


def format_symbol_text(name: str, type: str, source: str, file_path: str) -> str:
    """Format a symbol into text suitable for embedding.

    Combines the symbol metadata with source code to create
    a rich text representation for semantic search.
    """
    return f"{type} {name} in {file_path}\n{source}"


def generate_embeddings_from_texts(
    texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 32,
) -> list[list[float]]:
    """Generate embeddings from raw text strings.

    Args:
        texts: List of text strings to embed.
        model_name: SentenceTransformer model to use.
        batch_size: Number of texts to embed per batch.

    Returns:
        List of embedding vectors (list of floats), one per input text.
    """
    if not texts:
        return []

    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


def generate_embeddings(
    symbols: list[dict],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 32,
) -> list[EmbeddingResult]:
    """Generate embeddings for a list of symbols.

    Args:
        symbols: List of dicts with keys: symbol_id, name, type, source, file_path
        model_name: SentenceTransformer model to use.
        batch_size: Number of symbols to embed per batch.

    Returns:
        List of EmbeddingResult with symbol_id and embedding vector.
    """
    if not symbols:
        return []

    model = SentenceTransformer(model_name)

    texts = [
        format_symbol_text(
            name=sym["name"],
            type=sym["type"],
            source=sym["source"],
            file_path=sym["file_path"],
        )
        for sym in symbols
    ]

    results = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_symbols = symbols[i : i + batch_size]
        embeddings = model.encode(batch_texts, show_progress_bar=False)

        for sym, emb in zip(batch_symbols, embeddings):
            results.append(EmbeddingResult(
                symbol_id=sym["symbol_id"],
                embedding=emb.tolist(),
            ))

    return results
