"""Semantic vector search via Qdrant."""

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover – library absent in test environments
    SentenceTransformer = None  # type: ignore[assignment,misc]

from retrieval import SymbolMatch


def embed_queries(queries: list, model_name: str = "all-MiniLM-L6-v2") -> list:
    """Encode a list of query strings into embedding vectors.

    Args:
        queries: Natural-language query strings to embed.
        model_name: SentenceTransformer model identifier.

    Returns:
        List of float lists, one per query, in the same order.
    """
    model = SentenceTransformer(model_name)
    raw = model.encode(queries)
    return [list(float(v) for v in vec) for vec in raw]


def search_single_query(
    qdrant,
    query_vector: list,
    repo: str,
    top_k: int = 20,
    module: str | None = None,
    filters: dict | None = None,
) -> list:
    """Search Qdrant with a single embedding vector.

    Args:
        qdrant: QdrantVectorStore instance.
        query_vector: Embedding vector for the query.
        repo: Repository name used as a filter.
        top_k: Maximum number of results to retrieve.
        module: Optional module name to narrow the search scope.
        filters: Optional extra payload filters merged with repo/module.

    Returns:
        List of SymbolMatch objects with source="vector".
    """
    query_filters = {"repo": repo}
    if module:
        query_filters["module"] = module
    if filters:
        query_filters.update(filters)
    hits = qdrant.search(
        query_vector=query_vector,
        top_k=top_k,
        filters=query_filters,
    )
    return [_hit_to_symbol_match(hit) for hit in hits]


def merge_vector_results(results_per_query: list) -> list:
    """Deduplicate and merge SymbolMatch lists from multiple queries.

    For each unique symbol_id the base score is the maximum score seen across
    all queries.  Symbols that appear in more than one query receive a boost:

        final_score = min(1.0, max_score + 0.05 * (hit_count - 1))

    Args:
        results_per_query: List of SymbolMatch lists, one list per query.

    Returns:
        Deduplicated list sorted by score descending.
    """
    # Accumulate per symbol: best match object, best score, hit count
    best: dict = {}
    hit_counts: dict = {}

    for query_results in results_per_query:
        for match in query_results:
            sid = match.symbol_id
            if sid not in best or match.score > best[sid].score:
                best[sid] = match
            hit_counts[sid] = hit_counts.get(sid, 0) + 1

    merged = []
    for sid, match in best.items():
        count = hit_counts[sid]
        boosted_score = min(1.0, match.score + 0.05 * (count - 1))
        # Return a new SymbolMatch with the boosted score to avoid mutating input
        merged.append(
            SymbolMatch(
                symbol_id=match.symbol_id,
                name=match.name,
                type=match.type,
                file_path=match.file_path,
                repo=match.repo,
                start_line=match.start_line,
                end_line=match.end_line,
                score=boosted_score,
                source=match.source,
                module=match.module,
            )
        )

    merged.sort(key=lambda m: m.score, reverse=True)
    return merged


def search_multiple_queries(
    qdrant,
    queries: list,
    repo: str,
    model_name: str = "all-MiniLM-L6-v2",
    top_k_per_query: int = 20,
    module: str | None = None,
) -> list:
    """Full vector search pipeline: embed -> search each query -> merge.

    Args:
        qdrant: QdrantVectorStore instance.
        queries: List of natural-language query strings.
        repo: Repository name to filter results.
        model_name: SentenceTransformer model identifier.
        top_k_per_query: Number of Qdrant results to retrieve per query.
        module: Optional module name to narrow the search scope.

    Returns:
        Deduplicated, boosted, and sorted list of SymbolMatch objects.
    """
    vectors = embed_queries(queries, model_name=model_name)
    results_per_query = [
        search_single_query(qdrant, vec, repo=repo, top_k=top_k_per_query, module=module)
        for vec in vectors
    ]
    return merge_vector_results(results_per_query)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _hit_to_symbol_match(hit: dict) -> SymbolMatch:
    """Convert a raw Qdrant hit dict to a SymbolMatch."""
    payload = hit["payload"]
    return SymbolMatch(
        symbol_id=hit["symbol_id"],
        name=payload["symbol_name"],
        type=payload["symbol_type"],
        file_path=payload["file_path"],
        repo=payload["repo"],
        start_line=payload["start_line"],
        end_line=payload["end_line"],
        score=float(hit["score"]),
        source="vector",
        module=payload.get("module", ""),
    )
