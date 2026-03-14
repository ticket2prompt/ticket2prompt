"""Unit tests for workflows/langgraph_pipeline.py."""

from unittest.mock import MagicMock, patch

import pytest

from prompts import CompressedContext, CodeSnippet, GeneratedPrompt
from retrieval import FileCandidate, SymbolMatch, TicketInput
from workflows.langgraph_pipeline import build_pipeline, run_pipeline
from workflows.pipeline_steps import PipelineConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ticket():
    return TicketInput(
        title="Add payment retry",
        description="Implement exponential backoff for Stripe 5xx errors.",
        acceptance_criteria="Retry up to 3 times.",
        repo="payments-service",
    )


@pytest.fixture
def mock_config():
    return PipelineConfig(
        postgres=MagicMock(),
        qdrant=MagicMock(),
        cache=MagicMock(),
        llm_fn=MagicMock(return_value="query one\nquery two"),
    )


# ---------------------------------------------------------------------------
# build_pipeline
# ---------------------------------------------------------------------------


def test_build_pipeline_returns_runnable(mock_config):
    app = build_pipeline(mock_config)
    assert hasattr(app, "invoke"), "Compiled graph must have an invoke method"


def test_pipeline_graph_has_all_nodes(mock_config):
    app = build_pipeline(mock_config)
    # LangGraph compiled graph exposes node names via .get_graph().nodes
    graph = app.get_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "intake", "expansion", "embedding", "vector_search",
        "keyword_search", "graph_expansion", "ranking",
        "compression", "prompt",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


# ---------------------------------------------------------------------------
# run_pipeline — end-to-end with mocked dependencies
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.generate_prompt")
@patch("workflows.pipeline_steps.compress_context")
@patch("workflows.pipeline_steps.rank_files")
@patch("workflows.pipeline_steps.graph_expansion")
@patch("workflows.pipeline_steps.keyword_search")
@patch("workflows.pipeline_steps.merge_vector_results")
@patch("workflows.pipeline_steps.search_single_query")
@patch("workflows.pipeline_steps.embed_queries")
@patch("workflows.pipeline_steps.expand_ticket")
def test_run_pipeline_end_to_end(
    mock_expand,
    mock_embed,
    mock_search,
    mock_merge,
    mock_kw,
    mock_graph,
    mock_rank,
    mock_compress,
    mock_gen,
    mock_config,
    sample_ticket,
):
    # Setup mocks for full pipeline flow
    sym = SymbolMatch(
        symbol_id="s1", name="pay", type="function",
        file_path="pay.py", repo="payments-service",
        start_line=1, end_line=10, score=0.9, source="vector",
    )
    fc = FileCandidate(
        file_path="pay.py", repo="payments-service",
        symbols=[sym], final_score=0.85,
    )
    snippet = CodeSnippet(
        file_path="pay.py", symbol_name="pay", symbol_type="function",
        start_line=1, end_line=10, content="def pay(): ...", token_count=5,
    )
    compressed = CompressedContext(
        snippets=[snippet], total_tokens=5, budget=5000,
        files_included=1, symbols_included=1,
    )
    prompt = GeneratedPrompt(
        prompt_text="## Task\nAdd payment retry",
        token_count=50,
        files_referenced=["pay.py"],
        symbols_referenced=["pay"],
    )

    mock_expand.return_value = ["query one", "query two"]
    mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
    mock_search.return_value = [sym]
    mock_merge.return_value = [sym]
    mock_kw.return_value = [sym]
    mock_graph.return_value = [sym]
    mock_rank.return_value = [fc]
    mock_config.postgres.get_file_content.return_value = "def pay(): ..."
    mock_compress.return_value = compressed
    mock_gen.return_value = prompt

    result = run_pipeline(mock_config, sample_ticket)

    assert result["generated_prompt"] == prompt
    assert result["repo"] == "payments-service"
    assert len(result.get("errors", [])) == 0


# ---------------------------------------------------------------------------
# Pipeline resilience
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.generate_prompt")
@patch("workflows.pipeline_steps.compress_context")
@patch("workflows.pipeline_steps.rank_files")
@patch("workflows.pipeline_steps.graph_expansion")
@patch("workflows.pipeline_steps.keyword_search")
@patch("workflows.pipeline_steps.merge_vector_results")
@patch("workflows.pipeline_steps.search_single_query")
@patch("workflows.pipeline_steps.embed_queries")
@patch("workflows.pipeline_steps.expand_ticket")
def test_pipeline_handles_empty_vector_results(
    mock_expand,
    mock_embed,
    mock_search,
    mock_merge,
    mock_kw,
    mock_graph,
    mock_rank,
    mock_compress,
    mock_gen,
    mock_config,
    sample_ticket,
):
    """Pipeline completes even when vector search returns nothing."""
    sym = SymbolMatch(
        symbol_id="s1", name="pay", type="function",
        file_path="pay.py", repo="payments-service",
        start_line=1, end_line=10, score=0.5, source="keyword",
    )
    fc = FileCandidate(
        file_path="pay.py", repo="payments-service",
        symbols=[sym], final_score=0.5,
    )
    prompt = GeneratedPrompt(prompt_text="prompt", token_count=10)

    mock_expand.return_value = ["q1"]
    mock_embed.return_value = [[0.1]]
    mock_search.return_value = []  # No vector results
    mock_merge.return_value = []
    mock_kw.return_value = [sym]
    mock_graph.return_value = []
    mock_rank.return_value = [fc]
    mock_config.postgres.get_file_content.return_value = "code"
    mock_compress.return_value = CompressedContext()
    mock_gen.return_value = prompt

    result = run_pipeline(mock_config, sample_ticket)
    assert result["generated_prompt"] == prompt


@patch("workflows.pipeline_steps.generate_prompt")
@patch("workflows.pipeline_steps.compress_context")
@patch("workflows.pipeline_steps.rank_files")
@patch("workflows.pipeline_steps.graph_expansion")
@patch("workflows.pipeline_steps.keyword_search")
@patch("workflows.pipeline_steps.merge_vector_results")
@patch("workflows.pipeline_steps.search_single_query")
@patch("workflows.pipeline_steps.embed_queries")
@patch("workflows.pipeline_steps.expand_ticket")
def test_pipeline_handles_graph_expansion_failure(
    mock_expand,
    mock_embed,
    mock_search,
    mock_merge,
    mock_kw,
    mock_graph,
    mock_rank,
    mock_compress,
    mock_gen,
    mock_config,
    sample_ticket,
):
    """Pipeline completes even when graph expansion fails."""
    prompt = GeneratedPrompt(prompt_text="prompt", token_count=10)

    mock_expand.return_value = ["q1"]
    mock_embed.return_value = [[0.1]]
    mock_search.return_value = []
    mock_merge.return_value = []
    mock_kw.return_value = []
    mock_graph.side_effect = RuntimeError("db error")
    mock_rank.return_value = []
    mock_config.postgres.get_file_content.return_value = None
    mock_compress.return_value = CompressedContext()
    mock_gen.return_value = prompt

    result = run_pipeline(mock_config, sample_ticket)
    assert result["generated_prompt"] == prompt
    assert any("graph expansion" in e.lower() for e in result.get("errors", []))
