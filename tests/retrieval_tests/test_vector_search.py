"""Unit tests for retrieval/vector_search.py.

All external dependencies (SentenceTransformer, QdrantVectorStore) are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from retrieval import SymbolMatch
from retrieval.vector_search import (
    embed_queries,
    merge_vector_results,
    search_multiple_queries,
    search_single_query,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_qdrant_hit(symbol_id: str, score: float, **payload_overrides) -> dict:
    """Build a fake Qdrant search result dict."""
    payload = {
        "symbol_name": "my_func",
        "symbol_type": "function",
        "file_path": "src/foo.py",
        "repo": "my-repo",
        "start_line": 10,
        "end_line": 20,
        "language": "python",
    }
    payload.update(payload_overrides)
    return {"symbol_id": symbol_id, "score": score, "payload": payload}


def _make_symbol_match(symbol_id: str, score: float, **kwargs) -> SymbolMatch:
    defaults = dict(
        name="my_func",
        type="function",
        file_path="src/foo.py",
        repo="my-repo",
        start_line=10,
        end_line=20,
        source="vector",
    )
    defaults.update(kwargs)
    return SymbolMatch(symbol_id=symbol_id, score=score, **defaults)


# ---------------------------------------------------------------------------
# embed_queries
# ---------------------------------------------------------------------------

class TestEmbedQueries:
    def test_embed_queries_returns_correct_count(self):
        """3 queries → 3 embedding vectors."""
        fake_vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vectors

        with patch("retrieval.vector_search.SentenceTransformer", return_value=mock_model):
            result = embed_queries(["q1", "q2", "q3"])

        assert len(result) == 3

    def test_embed_queries_returns_float_lists(self):
        """Each embedding is a list of floats."""
        fake_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vectors

        with patch("retrieval.vector_search.SentenceTransformer", return_value=mock_model):
            result = embed_queries(["hello", "world"])

        for vec in result:
            assert isinstance(vec, list)
            for val in vec:
                assert isinstance(val, float)


# ---------------------------------------------------------------------------
# search_single_query
# ---------------------------------------------------------------------------

class TestSearchSingleQuery:
    def test_search_single_query_maps_qdrant_results(self):
        """Qdrant result dicts are correctly mapped to SymbolMatch objects."""
        hit = _make_qdrant_hit(
            "sym-1",
            0.92,
            symbol_name="calculate_total",
            symbol_type="function",
            file_path="src/billing.py",
            repo="billing-repo",
            start_line=5,
            end_line=25,
        )
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [hit]

        results = search_single_query(mock_qdrant, [0.1, 0.2], repo="billing-repo")

        assert len(results) == 1
        match = results[0]
        assert isinstance(match, SymbolMatch)
        assert match.symbol_id == "sym-1"
        assert match.name == "calculate_total"
        assert match.type == "function"
        assert match.file_path == "src/billing.py"
        assert match.repo == "billing-repo"
        assert match.start_line == 5
        assert match.end_line == 25
        assert match.score == pytest.approx(0.92)
        assert match.source == "vector"

    def test_search_single_query_applies_repo_filter(self):
        """qdrant.search is called with filters={"repo": repo}."""
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        search_single_query(mock_qdrant, [0.5, 0.6], repo="target-repo", top_k=10)

        mock_qdrant.search.assert_called_once()
        _, kwargs = mock_qdrant.search.call_args
        assert kwargs.get("filters") == {"repo": "target-repo"}
        assert kwargs.get("top_k") == 10

    def test_search_single_query_empty_results(self):
        """Empty Qdrant response returns an empty list."""
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        results = search_single_query(mock_qdrant, [0.1], repo="any-repo")

        assert results == []


# ---------------------------------------------------------------------------
# merge_vector_results
# ---------------------------------------------------------------------------

class TestMergeVectorResults:
    def test_merge_vector_results_deduplicates(self):
        """Same symbol_id appearing in two query result lists appears once."""
        list_a = [_make_symbol_match("sym-1", 0.8)]
        list_b = [_make_symbol_match("sym-1", 0.7)]

        merged = merge_vector_results([list_a, list_b])

        ids = [m.symbol_id for m in merged]
        assert ids.count("sym-1") == 1

    def test_merge_vector_results_takes_max_score(self):
        """When deduplicating, the higher raw score is retained before boost."""
        list_a = [_make_symbol_match("sym-1", 0.8)]
        list_b = [_make_symbol_match("sym-1", 0.5)]

        merged = merge_vector_results([list_a, list_b])

        # hit_count=2 → boost = 0.05*(2-1)=0.05, base max_score=0.8
        # final = min(1.0, 0.8 + 0.05) = 0.85
        assert merged[0].score == pytest.approx(0.85)

    def test_merge_vector_results_boosts_multi_query_hits(self):
        """Symbol appearing in 3 queries gets boost of 0.05*(3-1)=0.10."""
        sym = _make_symbol_match("sym-1", 0.7)
        merged = merge_vector_results([[sym], [sym], [sym]])

        expected = min(1.0, 0.7 + 0.05 * (3 - 1))
        assert merged[0].score == pytest.approx(expected)

    def test_merge_vector_results_boost_capped_at_one(self):
        """Score boost is capped at 1.0."""
        sym = _make_symbol_match("sym-1", 0.98)
        merged = merge_vector_results([[sym], [sym], [sym]])

        assert merged[0].score == pytest.approx(1.0)

    def test_merge_vector_results_single_query(self):
        """Single query list passes through unchanged (no merging needed)."""
        symbols = [
            _make_symbol_match("sym-a", 0.9),
            _make_symbol_match("sym-b", 0.6),
        ]
        merged = merge_vector_results([symbols])

        ids = {m.symbol_id for m in merged}
        assert ids == {"sym-a", "sym-b"}
        # No boost for single-query hits (hit_count=1 → 0.05*0 = 0)
        scores = {m.symbol_id: m.score for m in merged}
        assert scores["sym-a"] == pytest.approx(0.9)
        assert scores["sym-b"] == pytest.approx(0.6)

    def test_merge_vector_results_sorted_descending(self):
        """Merged results are sorted by score descending."""
        list_a = [_make_symbol_match("sym-low", 0.4)]
        list_b = [_make_symbol_match("sym-high", 0.95)]

        merged = merge_vector_results([list_a, list_b])

        scores = [m.score for m in merged]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# search_multiple_queries (end-to-end with mocks)
# ---------------------------------------------------------------------------

class TestSearchMultipleQueries:
    def test_search_multiple_queries_end_to_end(self):
        """Embeds queries, calls search for each, merges and returns SymbolMatches."""
        queries = ["add payment method", "billing module"]
        fake_vectors = [[0.1, 0.2], [0.3, 0.4]]

        hit_q1 = _make_qdrant_hit("sym-1", 0.9, symbol_name="add_payment")
        hit_q2 = _make_qdrant_hit("sym-1", 0.7, symbol_name="add_payment")
        hit_q2_unique = _make_qdrant_hit("sym-2", 0.6, symbol_name="process_billing")

        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vectors

        mock_qdrant = MagicMock()
        mock_qdrant.search.side_effect = [
            [hit_q1],
            [hit_q2, hit_q2_unique],
        ]

        with patch("retrieval.vector_search.SentenceTransformer", return_value=mock_model):
            results = search_multiple_queries(
                mock_qdrant, queries, repo="pay-repo", top_k_per_query=20
            )

        # sym-1 appears in both queries → deduplicated, boosted
        # sym-2 appears in one query only
        ids = [m.symbol_id for m in results]
        assert ids.count("sym-1") == 1
        assert "sym-2" in ids

        sym1 = next(m for m in results if m.symbol_id == "sym-1")
        # max_score=0.9, hit_count=2 → min(1.0, 0.9 + 0.05) = 0.95
        assert sym1.score == pytest.approx(0.95)

        # Results sorted descending
        scores = [m.score for m in results]
        assert scores == sorted(scores, reverse=True)

        # qdrant.search called once per query
        assert mock_qdrant.search.call_count == 2

        # All sources labelled "vector"
        assert all(m.source == "vector" for m in results)


# ---------------------------------------------------------------------------
# Module filtering
# ---------------------------------------------------------------------------

class TestModuleFiltering:
    def test_search_single_query_with_module_filter(self):
        """Module filter is included in qdrant search filters when module is provided."""
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        search_single_query(mock_qdrant, [0.1], repo="my-repo", module="payments")

        mock_qdrant.search.assert_called_once()
        _, kwargs = mock_qdrant.search.call_args
        assert kwargs["filters"] == {"repo": "my-repo", "module": "payments"}

    def test_search_single_query_without_module(self):
        """Without module, only repo filter is used (backward compatibility)."""
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        search_single_query(mock_qdrant, [0.1], repo="my-repo")

        mock_qdrant.search.assert_called_once()
        _, kwargs = mock_qdrant.search.call_args
        assert kwargs["filters"] == {"repo": "my-repo"}
        assert "module" not in kwargs["filters"]

    def test_search_single_query_module_none_omitted(self):
        """Explicitly passing module=None does not add module key to filters."""
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        search_single_query(mock_qdrant, [0.1], repo="my-repo", module=None)

        _, kwargs = mock_qdrant.search.call_args
        assert kwargs["filters"] == {"repo": "my-repo"}

    def test_search_multiple_queries_with_module(self):
        """Module parameter is passed through to each search_single_query call."""
        fake_vectors = [[0.1, 0.2], [0.3, 0.4]]
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vectors

        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        with patch("retrieval.vector_search.SentenceTransformer", return_value=mock_model):
            search_multiple_queries(
                mock_qdrant, ["query one", "query two"],
                repo="my-repo", module="billing",
            )

        assert mock_qdrant.search.call_count == 2
        for call in mock_qdrant.search.call_args_list:
            _, kwargs = call
            assert kwargs["filters"] == {"repo": "my-repo", "module": "billing"}

    def test_hit_to_symbol_match_preserves_module(self):
        """_hit_to_symbol_match extracts module from payload."""
        hit = _make_qdrant_hit("sym-1", 0.8, module="payments")
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [hit]

        results = search_single_query(mock_qdrant, [0.1], repo="my-repo")

        assert len(results) == 1
        assert results[0].module == "payments"

    def test_hit_to_symbol_match_module_defaults_empty(self):
        """_hit_to_symbol_match defaults module to empty string when absent from payload."""
        hit = _make_qdrant_hit("sym-1", 0.8)  # no module in payload
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [hit]

        results = search_single_query(mock_qdrant, [0.1], repo="my-repo")

        assert results[0].module == ""

    def test_merge_vector_results_preserves_module(self):
        """merge_vector_results carries the module field through to merged results."""
        sym = _make_symbol_match("sym-1", 0.8, module="payments")
        merged = merge_vector_results([[sym]])

        assert merged[0].module == "payments"
