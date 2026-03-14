"""Tests for prompts/prompt_generator.py."""

from unittest.mock import MagicMock, patch, call
import pytest

from prompts import CodeSnippet, CompressedContext, GeneratedPrompt
from retrieval import TicketInput, FileCandidate, SymbolMatch, RetrievalResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_ticket(title="Fix auth bug", description="Auth fails on timeout", repo="my-repo"):
    return TicketInput(title=title, description=description, repo=repo)


def make_file_candidate(file_path="src/auth.py", repo="my-repo", score=0.9):
    symbol = SymbolMatch(
        symbol_id="sym-1",
        name="authenticate",
        type="function",
        file_path=file_path,
        repo=repo,
        start_line=10,
        end_line=30,
        score=score,
    )
    return FileCandidate(file_path=file_path, repo=repo, symbols=[symbol], final_score=score)


def make_snippet(file_path="src/auth.py", symbol_name="authenticate", symbol_type="function"):
    return CodeSnippet(
        file_path=file_path,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        start_line=10,
        end_line=30,
        content="def authenticate(): pass",
        token_count=50,
    )


def make_compressed_context(snippets=None, total_tokens=200, budget=4000):
    if snippets is None:
        snippets = [make_snippet()]
    return CompressedContext(
        snippets=snippets,
        total_tokens=total_tokens,
        budget=budget,
        files_included=len({s.file_path for s in snippets}),
        symbols_included=len(snippets),
    )


# ---------------------------------------------------------------------------
# generate_prompt — normal case
# ---------------------------------------------------------------------------

class TestGeneratePromptNormal:
    def test_returns_generated_prompt(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "def authenticate(): pass"}

        ctx = make_compressed_context()
        prompt_text = "This is the assembled prompt."

        with patch("prompts.prompt_generator.compress_context", return_value=ctx) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value=prompt_text) as mock_ap, \
             patch("prompts.prompt_generator.estimate_tokens", return_value=150):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert isinstance(result, GeneratedPrompt)
        assert result.prompt_text == prompt_text
        assert result.token_count == 150

    def test_files_referenced_populated(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "def authenticate(): pass"}

        snippets = [
            make_snippet("src/auth.py", "authenticate"),
            make_snippet("src/utils.py", "helper"),
        ]
        ctx = make_compressed_context(snippets=snippets)

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert set(result.files_referenced) == {"src/auth.py", "src/utils.py"}

    def test_symbols_referenced_populated(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "def authenticate(): pass"}

        snippets = [
            make_snippet("src/auth.py", "authenticate"),
            make_snippet("src/utils.py", "helper"),
        ]
        ctx = make_compressed_context(snippets=snippets)

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert set(result.symbols_referenced) == {"authenticate", "helper"}

    def test_files_referenced_unique(self):
        """Duplicate file paths in snippets should appear only once."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "def authenticate(): pass"}

        snippets = [
            make_snippet("src/auth.py", "authenticate"),
            make_snippet("src/auth.py", "logout"),
        ]
        ctx = make_compressed_context(snippets=snippets)

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert result.files_referenced.count("src/auth.py") == 1

    def test_symbols_referenced_unique(self):
        """Duplicate symbol names in snippets should appear only once."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "def authenticate(): pass"}

        snippets = [
            make_snippet("src/auth.py", "authenticate"),
            make_snippet("src/utils.py", "authenticate"),  # same name, different file
        ]
        ctx = make_compressed_context(snippets=snippets)

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert result.symbols_referenced.count("authenticate") == 1

    def test_compress_context_called_with_correct_args(self):
        from prompts.prompt_generator import generate_prompt
        from prompts.context_compression import DEFAULT_TOKEN_BUDGET

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}
        ctx = make_compressed_context()

        with patch("prompts.prompt_generator.compress_context", return_value=ctx) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            generate_prompt(ticket, ranked_files, file_contents)

        mock_cc.assert_called_once_with(ranked_files, file_contents, DEFAULT_TOKEN_BUDGET)

    def test_assemble_prompt_called_with_correct_args(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}
        ctx = make_compressed_context()

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt") as mock_ap, \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            generate_prompt(ticket, ranked_files, file_contents)

        mock_ap.assert_called_once_with(ticket, ctx, ticket.repo)

    def test_custom_token_budget_passed_to_compress_context(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}
        ctx = make_compressed_context()

        with patch("prompts.prompt_generator.compress_context", return_value=ctx) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=100):

            generate_prompt(ticket, ranked_files, file_contents, token_budget=2000)

        mock_cc.assert_called_once_with(ranked_files, file_contents, 2000)


# ---------------------------------------------------------------------------
# generate_prompt — empty ranked_files
# ---------------------------------------------------------------------------

class TestGeneratePromptEmptyFiles:
    def test_empty_ranked_files(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        file_contents = {}
        ctx = make_compressed_context(snippets=[])

        with patch("prompts.prompt_generator.compress_context", return_value=ctx) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="empty prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=50):

            result = generate_prompt(ticket, [], file_contents)

        assert result.files_referenced == []
        assert result.symbols_referenced == []
        assert result.prompt_text == "empty prompt"
        mock_cc.assert_called_once_with([], file_contents, pytest.approx(mock_cc.call_args[0][2]))

    def test_none_ranked_files_treated_as_empty(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        file_contents = {}
        ctx = make_compressed_context(snippets=[])

        with patch("prompts.prompt_generator.compress_context", return_value=ctx) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=50):

            result = generate_prompt(ticket, None, file_contents)

        # Should not raise; compress_context called with empty list
        call_args = mock_cc.call_args[0]
        assert call_args[0] == []


# ---------------------------------------------------------------------------
# generate_prompt — token budget exceeded / retry
# ---------------------------------------------------------------------------

class TestGeneratePromptTokenBudgetRetry:
    def test_retries_with_reduced_budget_when_over_limit(self):
        """If token_count > token_budget, retry once with budget * 0.8."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}

        ctx_first = make_compressed_context(total_tokens=5000)
        ctx_second = make_compressed_context(total_tokens=3000)

        # First call returns over-budget result; second call returns acceptable result
        with patch("prompts.prompt_generator.compress_context", side_effect=[ctx_first, ctx_second]) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", side_effect=[5500, 3200]):

            result = generate_prompt(ticket, ranked_files, file_contents, token_budget=4000)

        assert mock_cc.call_count == 2
        first_budget = mock_cc.call_args_list[0][0][2]
        second_budget = mock_cc.call_args_list[1][0][2]
        assert second_budget == pytest.approx(first_budget * 0.8)

    def test_retry_uses_reduced_prompt_text(self):
        """After retry, the second prompt_text is returned."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}

        ctx_first = make_compressed_context(total_tokens=5000)
        ctx_second = make_compressed_context(total_tokens=3000)

        with patch("prompts.prompt_generator.compress_context", side_effect=[ctx_first, ctx_second]), \
             patch("prompts.prompt_generator.assemble_prompt", side_effect=["big prompt", "small prompt"]) as mock_ap, \
             patch("prompts.prompt_generator.estimate_tokens", side_effect=[5500, 3200]):

            result = generate_prompt(ticket, ranked_files, file_contents, token_budget=4000)

        assert result.prompt_text == "small prompt"
        assert result.token_count == 3200

    def test_no_retry_when_within_budget(self):
        """When token count is within budget, compress_context called only once."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}
        ctx = make_compressed_context(total_tokens=200)

        with patch("prompts.prompt_generator.compress_context", return_value=ctx) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=150):

            generate_prompt(ticket, ranked_files, file_contents, token_budget=4000)

        assert mock_cc.call_count == 1

    def test_only_retries_once(self):
        """Even if retry still exceeds budget, does not retry a third time."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate()]
        file_contents = {"src/auth.py": "content"}

        ctx_first = make_compressed_context(total_tokens=5000)
        ctx_second = make_compressed_context(total_tokens=4500)

        with patch("prompts.prompt_generator.compress_context", side_effect=[ctx_first, ctx_second]) as mock_cc, \
             patch("prompts.prompt_generator.assemble_prompt", return_value="prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", side_effect=[5500, 4800]):

            result = generate_prompt(ticket, ranked_files, file_contents, token_budget=4000)

        assert mock_cc.call_count == 2  # no third retry


# ---------------------------------------------------------------------------
# generate_prompt — input validation
# ---------------------------------------------------------------------------

class TestGeneratePromptValidation:
    def test_empty_title_raises_value_error(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket(title="")
        with pytest.raises(ValueError, match="Ticket title is required"):
            generate_prompt(ticket, [], {})

    def test_whitespace_only_title_raises_value_error(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket(title="   ")
        with pytest.raises(ValueError, match="Ticket title is required"):
            generate_prompt(ticket, [], {})


# ---------------------------------------------------------------------------
# generate_prompt — edge cases
# ---------------------------------------------------------------------------

class TestGeneratePromptEdgeCases:
    def test_all_files_missing_from_contents(self):
        """If file_contents is empty, still calls through correctly."""
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate("src/auth.py")]
        file_contents = {}  # nothing loaded
        ctx = make_compressed_context(snippets=[])

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="minimal prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=20):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert result.prompt_text == "minimal prompt"
        assert result.files_referenced == []
        assert result.symbols_referenced == []

    def test_single_file_single_symbol(self):
        from prompts.prompt_generator import generate_prompt

        ticket = make_ticket()
        ranked_files = [make_file_candidate("src/main.py")]
        file_contents = {"src/main.py": "def main(): pass"}

        snippets = [make_snippet("src/main.py", "main")]
        ctx = make_compressed_context(snippets=snippets)

        with patch("prompts.prompt_generator.compress_context", return_value=ctx), \
             patch("prompts.prompt_generator.assemble_prompt", return_value="single prompt"), \
             patch("prompts.prompt_generator.estimate_tokens", return_value=80):

            result = generate_prompt(ticket, ranked_files, file_contents)

        assert result.files_referenced == ["src/main.py"]
        assert result.symbols_referenced == ["main"]
        assert result.prompt_text == "single prompt"
        assert result.token_count == 80


# ---------------------------------------------------------------------------
# generate_prompt_from_retrieval
# ---------------------------------------------------------------------------

class TestGeneratePromptFromRetrieval:
    def _make_retrieval_result(self, file_paths=None):
        if file_paths is None:
            file_paths = ["src/auth.py", "src/utils.py"]
        ranked_files = [make_file_candidate(fp) for fp in file_paths]
        return RetrievalResult(ranked_files=ranked_files, ranked_symbols=[], query_count=1, total_candidates=2)

    def test_loads_file_contents_from_postgres(self):
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        retrieval = self._make_retrieval_result(["src/auth.py", "src/utils.py"])

        postgres = MagicMock()
        postgres.get_file_content.side_effect = lambda fp, repo: f"content of {fp}"

        expected_prompt = GeneratedPrompt(prompt_text="final", token_count=100)

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt) as mock_gp:
            result = generate_prompt_from_retrieval(ticket, retrieval, postgres)

        assert result is expected_prompt
        assert postgres.get_file_content.call_count == 2

    def test_file_contents_passed_to_generate_prompt(self):
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        retrieval = self._make_retrieval_result(["src/auth.py"])

        postgres = MagicMock()
        postgres.get_file_content.return_value = "def authenticate(): pass"

        expected_prompt = GeneratedPrompt(prompt_text="out")

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt) as mock_gp:
            generate_prompt_from_retrieval(ticket, retrieval, postgres)

        call_kwargs = mock_gp.call_args
        file_contents_arg = call_kwargs[0][2] if len(call_kwargs[0]) > 2 else call_kwargs[1].get("file_contents")
        assert file_contents_arg == {"src/auth.py": "def authenticate(): pass"}

    def test_skips_files_where_get_file_content_returns_none(self):
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        retrieval = self._make_retrieval_result(["src/auth.py", "src/missing.py"])

        postgres = MagicMock()
        postgres.get_file_content.side_effect = lambda fp, repo: (
            "auth content" if fp == "src/auth.py" else None
        )

        expected_prompt = GeneratedPrompt(prompt_text="out")

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt) as mock_gp:
            generate_prompt_from_retrieval(ticket, retrieval, postgres)

        call_kwargs = mock_gp.call_args
        file_contents_arg = call_kwargs[0][2] if len(call_kwargs[0]) > 2 else call_kwargs[1].get("file_contents")
        assert "src/missing.py" not in file_contents_arg
        assert file_contents_arg == {"src/auth.py": "auth content"}

    def test_all_files_missing_returns_empty_contents(self):
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        retrieval = self._make_retrieval_result(["src/auth.py"])

        postgres = MagicMock()
        postgres.get_file_content.return_value = None

        expected_prompt = GeneratedPrompt(prompt_text="out")

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt) as mock_gp:
            generate_prompt_from_retrieval(ticket, retrieval, postgres)

        call_kwargs = mock_gp.call_args
        file_contents_arg = call_kwargs[0][2] if len(call_kwargs[0]) > 2 else call_kwargs[1].get("file_contents")
        assert file_contents_arg == {}

    def test_unique_file_paths_queried(self):
        """If ranked_files contains duplicate paths, query postgres only once per unique path."""
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        # Two FileCandidate objects with the same path
        ranked_files = [
            make_file_candidate("src/auth.py"),
            make_file_candidate("src/auth.py"),
        ]
        retrieval = RetrievalResult(ranked_files=ranked_files, ranked_symbols=[], query_count=1, total_candidates=2)

        postgres = MagicMock()
        postgres.get_file_content.return_value = "auth content"

        expected_prompt = GeneratedPrompt(prompt_text="out")

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt):
            generate_prompt_from_retrieval(ticket, retrieval, postgres)

        assert postgres.get_file_content.call_count == 1

    def test_passes_token_budget_through(self):
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        retrieval = self._make_retrieval_result(["src/auth.py"])

        postgres = MagicMock()
        postgres.get_file_content.return_value = "content"

        expected_prompt = GeneratedPrompt(prompt_text="out")

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt) as mock_gp:
            generate_prompt_from_retrieval(ticket, retrieval, postgres, token_budget=3000)

        # token_budget should be passed as keyword or positional arg
        call_args, call_kwargs = mock_gp.call_args
        budget_passed = call_kwargs.get("token_budget") or (call_args[3] if len(call_args) > 3 else None)
        assert budget_passed == 3000

    def test_ranked_files_passed_to_generate_prompt(self):
        from prompts.prompt_generator import generate_prompt_from_retrieval

        ticket = make_ticket()
        ranked_files = [make_file_candidate("src/auth.py")]
        retrieval = RetrievalResult(ranked_files=ranked_files, ranked_symbols=[], query_count=1, total_candidates=1)

        postgres = MagicMock()
        postgres.get_file_content.return_value = "content"

        expected_prompt = GeneratedPrompt(prompt_text="out")

        with patch("prompts.prompt_generator.generate_prompt", return_value=expected_prompt) as mock_gp:
            generate_prompt_from_retrieval(ticket, retrieval, postgres)

        call_args = mock_gp.call_args[0]
        assert call_args[1] == ranked_files
