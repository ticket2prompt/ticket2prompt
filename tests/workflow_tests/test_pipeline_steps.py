"""Unit tests for workflows/pipeline_steps.py."""

from unittest.mock import MagicMock, patch

import pytest

from retrieval import FileCandidate, SymbolMatch, TicketInput
from prompts import CompressedContext, CodeSnippet, GeneratedPrompt
from workflows.pipeline_steps import PipelineConfig, PipelineState, build_steps


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config():
    return PipelineConfig(
        postgres=MagicMock(),
        qdrant=MagicMock(),
        cache=MagicMock(),
        llm_fn=MagicMock(return_value="query one\nquery two\nquery three"),
        model_name="all-MiniLM-L6-v2",
        top_k_per_query=20,
        max_queries=6,
        graph_max_depth=2,
        file_limit=10,
        token_budget=5000,
    )


@pytest.fixture
def steps(mock_config):
    return build_steps(mock_config)


@pytest.fixture
def sample_ticket():
    return TicketInput(
        title="Add payment retry",
        description="Implement exponential backoff for Stripe 5xx errors.",
        acceptance_criteria="Retry up to 3 times.",
        comments=["Consider circuit breaker"],
        repo="payments-service",
    )


@pytest.fixture
def sample_symbol_match():
    return SymbolMatch(
        symbol_id="sym-1",
        name="process_payment",
        type="function",
        file_path="payments/service.py",
        repo="payments-service",
        start_line=10,
        end_line=30,
        score=0.9,
        source="vector",
    )


@pytest.fixture
def sample_file_candidate(sample_symbol_match):
    return FileCandidate(
        file_path="payments/service.py",
        repo="payments-service",
        symbols=[sample_symbol_match],
        final_score=0.85,
    )


# ---------------------------------------------------------------------------
# intake_step
# ---------------------------------------------------------------------------


def test_intake_step_sets_repo_and_errors(steps, sample_ticket):
    state = {"ticket": sample_ticket}
    result = steps["intake"](state)
    assert result["repo"] == "payments-service"
    assert result["errors"] == []


def test_intake_step_raises_on_empty_title(steps):
    ticket = TicketInput(title="", description="Some desc", repo="r")
    state = {"ticket": ticket}
    with pytest.raises(ValueError, match="title"):
        steps["intake"](state)


def test_intake_step_raises_on_whitespace_title(steps):
    ticket = TicketInput(title="   ", description="Some desc", repo="r")
    state = {"ticket": ticket}
    with pytest.raises(ValueError, match="title"):
        steps["intake"](state)


# ---------------------------------------------------------------------------
# expansion_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.expand_ticket")
def test_expansion_step_returns_queries(mock_expand, steps, sample_ticket):
    mock_expand.return_value = ["query one", "query two"]
    state = {"ticket": sample_ticket, "errors": []}
    result = steps["expansion"](state)
    assert result["expanded_queries"] == ["query one", "query two"]
    mock_expand.assert_called_once()


@patch("workflows.pipeline_steps.expand_ticket")
def test_expansion_step_passes_config_params(mock_expand, mock_config, sample_ticket):
    mock_expand.return_value = ["q1"]
    s = build_steps(mock_config)
    state = {"ticket": sample_ticket, "errors": []}
    s["expansion"](state)
    _, kwargs = mock_expand.call_args
    assert kwargs["llm_fn"] == mock_config.llm_fn
    assert kwargs["cache"] == mock_config.cache
    assert kwargs["max_queries"] == mock_config.max_queries


# ---------------------------------------------------------------------------
# embedding_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.embed_queries")
def test_embedding_step_returns_vectors(mock_embed, steps):
    mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
    state = {"expanded_queries": ["q1", "q2"], "errors": []}
    result = steps["embedding"](state)
    assert result["query_embeddings"] == [[0.1, 0.2], [0.3, 0.4]]


@patch("workflows.pipeline_steps.embed_queries")
def test_embedding_step_returns_empty_on_failure(mock_embed, steps):
    mock_embed.side_effect = RuntimeError("model error")
    state = {"expanded_queries": ["q1"], "errors": []}
    result = steps["embedding"](state)
    assert result["query_embeddings"] == []
    assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# vector_search_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.merge_vector_results")
@patch("workflows.pipeline_steps.search_single_query")
def test_vector_search_step_merges_results(
    mock_search, mock_merge, steps, sample_symbol_match, mock_config
):
    mock_search.return_value = [sample_symbol_match]
    mock_merge.return_value = [sample_symbol_match]
    state = {
        "query_embeddings": [[0.1, 0.2]],
        "repo": "payments-service",
        "errors": [],
    }
    result = steps["vector_search"](state)
    assert result["vector_matches"] == [sample_symbol_match]
    mock_search.assert_called_once_with(
        mock_config.qdrant,
        query_vector=[0.1, 0.2],
        repo="payments-service",
        top_k=mock_config.top_k_per_query,
        filters={"repo": "payments-service"},
    )


@patch("workflows.pipeline_steps.merge_vector_results")
@patch("workflows.pipeline_steps.search_single_query")
def test_vector_search_step_empty_embeddings(mock_search, mock_merge, steps):
    mock_merge.return_value = []
    state = {"query_embeddings": [], "repo": "r", "errors": []}
    result = steps["vector_search"](state)
    assert result["vector_matches"] == []
    mock_search.assert_not_called()


# ---------------------------------------------------------------------------
# keyword_search_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.keyword_search")
def test_keyword_search_step_returns_matches(
    mock_kw, steps, sample_ticket, sample_symbol_match, mock_config
):
    mock_kw.return_value = [sample_symbol_match]
    state = {"ticket": sample_ticket, "repo": "payments-service", "errors": []}
    result = steps["keyword_search"](state)
    assert result["keyword_matches"] == [sample_symbol_match]
    mock_kw.assert_called_once_with(
        mock_config.postgres,
        ticket=sample_ticket,
        repo="payments-service",
        org_id=mock_config.org_id,
        project_id=mock_config.project_id,
    )


# ---------------------------------------------------------------------------
# graph_expansion_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.graph_expansion")
def test_graph_expansion_step_expands(
    mock_graph, steps, sample_symbol_match, mock_config
):
    expanded = SymbolMatch(
        symbol_id="sym-2", name="retry_payment", type="function",
        file_path="payments/retry.py", repo="payments-service",
        start_line=1, end_line=10, score=0.7, source="graph",
    )
    mock_graph.return_value = [expanded]
    state = {
        "vector_matches": [sample_symbol_match],
        "keyword_matches": [],
        "errors": [],
    }
    result = steps["graph_expansion"](state)
    assert result["graph_matches"] == [expanded]
    mock_graph.assert_called_once_with(
        mock_config.postgres,
        initial_matches=[sample_symbol_match],
        max_depth=mock_config.graph_max_depth,
        org_id=mock_config.org_id,
        project_id=mock_config.project_id,
    )


@patch("workflows.pipeline_steps.graph_expansion")
def test_graph_expansion_step_fallback_on_failure(mock_graph, steps, sample_symbol_match):
    mock_graph.side_effect = RuntimeError("db error")
    state = {
        "vector_matches": [sample_symbol_match],
        "keyword_matches": [],
        "errors": [],
    }
    result = steps["graph_expansion"](state)
    assert result["graph_matches"] == []
    assert len(result["errors"]) == 1
    assert "graph expansion" in result["errors"][0].lower()


# ---------------------------------------------------------------------------
# ranking_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.rank_files")
def test_ranking_step_ranks_files(
    mock_rank, steps, sample_file_candidate, sample_symbol_match, mock_config
):
    mock_rank.return_value = [sample_file_candidate]
    state = {
        "vector_matches": [sample_symbol_match],
        "keyword_matches": [],
        "graph_matches": [],
        "repo": "payments-service",
        "errors": [],
    }
    result = steps["ranking"](state)
    assert result["ranked_files"] == [sample_file_candidate]
    mock_rank.assert_called_once_with(
        vector_matches=[sample_symbol_match],
        keyword_matches=[],
        graph_matches=[],
        postgres=mock_config.postgres,
        repo="payments-service",
        file_limit=mock_config.file_limit,
        org_id=mock_config.org_id,
        project_id=mock_config.project_id,
    )


# ---------------------------------------------------------------------------
# compression_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.compress_context")
def test_compression_step_compresses(mock_compress, tmp_path, sample_file_candidate, mock_config):
    compressed = CompressedContext(
        snippets=[CodeSnippet(
            file_path="payments/service.py", symbol_name="process_payment",
            symbol_type="function", start_line=10, end_line=30,
            content="def process_payment(): ...", token_count=10,
        )],
        total_tokens=10, budget=5000, files_included=1, symbols_included=1,
    )
    mock_compress.return_value = compressed

    # Create the file on disk so the compression step can read it
    file_dir = tmp_path / "payments"
    file_dir.mkdir()
    (file_dir / "service.py").write_text("def process_payment(): ...")

    mock_config.repo_base_path = str(tmp_path)
    steps_with_path = build_steps(mock_config)

    state = {
        "ranked_files": [sample_file_candidate],
        "repo": "payments-service",
        "errors": [],
    }
    result = steps_with_path["compression"](state)
    assert result["compressed_context"] == compressed
    assert "payments/service.py" in result["file_contents"]


@patch("workflows.pipeline_steps.compress_context")
def test_compression_step_skips_missing_files(mock_compress, steps, sample_file_candidate, mock_config):
    mock_compress.return_value = CompressedContext()
    mock_config.postgres.get_file_content.return_value = None

    state = {
        "ranked_files": [sample_file_candidate],
        "repo": "payments-service",
        "errors": [],
    }
    result = steps["compression"](state)
    assert result["file_contents"] == {}


# ---------------------------------------------------------------------------
# prompt_step
# ---------------------------------------------------------------------------


@patch("workflows.pipeline_steps.generate_prompt")
def test_prompt_step_generates_prompt(mock_gen, steps, sample_ticket, sample_file_candidate):
    prompt = GeneratedPrompt(
        prompt_text="## Task\nAdd payment retry",
        token_count=50,
        files_referenced=["payments/service.py"],
        symbols_referenced=["process_payment"],
    )
    mock_gen.return_value = prompt
    state = {
        "ticket": sample_ticket,
        "ranked_files": [sample_file_candidate],
        "file_contents": {"payments/service.py": "def process_payment(): ..."},
        "errors": [],
    }
    result = steps["prompt"](state)
    assert result["generated_prompt"] == prompt
    mock_gen.assert_called_once()
