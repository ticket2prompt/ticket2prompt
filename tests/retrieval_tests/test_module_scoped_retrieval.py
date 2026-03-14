"""Tests for module-scoped retrieval via vector search."""

from unittest.mock import MagicMock, patch

import pytest

from retrieval import SymbolMatch
from retrieval.vector_search import search_multiple_queries, search_single_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_qdrant_hit(symbol_id: str, score: float, module: str = "", **payload_overrides) -> dict:
    """Build a fake Qdrant search result dict."""
    payload = {
        "symbol_name": "my_func",
        "symbol_type": "function",
        "file_path": "src/foo.py",
        "repo": "my-repo",
        "start_line": 10,
        "end_line": 20,
    }
    if module:
        payload["module"] = module
    payload.update(payload_overrides)
    return {"symbol_id": symbol_id, "score": score, "payload": payload}


# ---------------------------------------------------------------------------
# TestModuleScopedRetrieval
# ---------------------------------------------------------------------------


class TestModuleScopedRetrieval:
    def test_retrieval_scoped_to_single_module(self):
        """Vector search with module filter passes correct filters to Qdrant."""
        payments_hit = _make_qdrant_hit("sym-pay-1", 0.9, module="payments")
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [payments_hit]

        results = search_single_query(
            mock_qdrant, [0.1, 0.2], repo="my-repo", module="payments"
        )

        _, kwargs = mock_qdrant.search.call_args
        assert kwargs["filters"] == {"repo": "my-repo", "module": "payments"}

        assert len(results) == 1
        assert results[0].symbol_id == "sym-pay-1"
        assert results[0].module == "payments"

    def test_retrieval_with_no_module_returns_all(self):
        """Without module filter, all repo symbols are returned (backward compatibility)."""
        hit_a = _make_qdrant_hit("sym-1", 0.9, module="payments")
        hit_b = _make_qdrant_hit("sym-2", 0.8, module="email")
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [hit_a, hit_b]

        results = search_single_query(mock_qdrant, [0.1, 0.2], repo="my-repo")

        _, kwargs = mock_qdrant.search.call_args
        assert kwargs["filters"] == {"repo": "my-repo"}
        assert "module" not in kwargs["filters"]

        assert len(results) == 2

    def test_multi_query_module_scoped_deduplication(self):
        """Multi-query scoped search deduplicates symbols appearing in multiple queries."""
        fake_vectors = [[0.1, 0.2], [0.3, 0.4]]
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vectors

        hit_q1 = _make_qdrant_hit("sym-pay-1", 0.85, module="payments")
        hit_q2 = _make_qdrant_hit("sym-pay-1", 0.75, module="payments")
        hit_q2_unique = _make_qdrant_hit("sym-pay-2", 0.60, module="payments")

        mock_qdrant = MagicMock()
        mock_qdrant.search.side_effect = [
            [hit_q1],
            [hit_q2, hit_q2_unique],
        ]

        with patch("retrieval.vector_search.SentenceTransformer", return_value=mock_model):
            results = search_multiple_queries(
                mock_qdrant,
                ["add payment", "process card"],
                repo="my-repo",
                module="payments",
            )

        # Verify module filter was applied for every query
        for call in mock_qdrant.search.call_args_list:
            _, kwargs = call
            assert kwargs["filters"] == {"repo": "my-repo", "module": "payments"}

        # sym-pay-1 appears in both queries → deduplicated
        ids = [m.symbol_id for m in results]
        assert ids.count("sym-pay-1") == 1
        assert "sym-pay-2" in ids

        # Scores sorted descending
        scores = [m.score for m in results]
        assert scores == sorted(scores, reverse=True)

        # Module field preserved on all results
        assert all(m.module == "payments" for m in results)

    def test_module_field_empty_when_not_in_payload(self):
        """SymbolMatch.module is empty string when payload has no module key."""
        hit = _make_qdrant_hit("sym-1", 0.7)  # no module in payload
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [hit]

        results = search_single_query(mock_qdrant, [0.1], repo="my-repo")

        assert results[0].module == ""

    def test_ticket_input_module_field_default(self):
        """TicketInput.module defaults to empty string for backward compatibility."""
        from retrieval import TicketInput

        ticket = TicketInput(title="Fix bug", description="Something is broken", repo="my-repo")
        assert ticket.module == ""

    def test_ticket_input_module_field_set(self):
        """TicketInput.module can be set to scope retrieval to a specific module."""
        from retrieval import TicketInput

        ticket = TicketInput(
            title="Fix payment bug",
            description="Charge fails",
            repo="my-repo",
            module="payments",
        )
        assert ticket.module == "payments"

    def test_symbol_match_module_field_default(self):
        """SymbolMatch.module defaults to empty string."""
        match = SymbolMatch(
            symbol_id="sym-1",
            name="my_func",
            type="function",
            file_path="src/foo.py",
            repo="my-repo",
            start_line=1,
            end_line=10,
            score=0.9,
        )
        assert match.module == ""
