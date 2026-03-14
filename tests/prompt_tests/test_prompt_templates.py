"""Tests for prompt_templates.py."""

import pytest
from prompts import CodeSnippet, CompressedContext
from prompts.prompt_templates import (
    format_task_section,
    format_repo_context_section,
    format_relevant_files_section,
    format_code_snippets_section,
    format_implementation_instructions_section,
    format_constraints_section,
    format_expected_behavior_section,
    assemble_prompt,
)
from retrieval import TicketInput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_ticket():
    return TicketInput(
        title="Add user authentication",
        description="Implement JWT-based authentication for the API.",
        acceptance_criteria="- Users can log in\n- Tokens expire after 1 hour",
        comments=["Consider using python-jose", "Check OWASP guidelines"],
        repo="my-repo",
    )


@pytest.fixture
def minimal_ticket():
    """Ticket with no acceptance_criteria and no comments."""
    return TicketInput(
        title="Fix null pointer bug",
        description="The service crashes when user_id is None.",
        repo="my-repo",
    )


@pytest.fixture
def snippet_a():
    return CodeSnippet(
        file_path="auth/jwt.py",
        symbol_name="create_token",
        symbol_type="function",
        start_line=10,
        end_line=25,
        content="def create_token(user_id: str) -> str:\n    pass",
        token_count=20,
    )


@pytest.fixture
def snippet_b():
    return CodeSnippet(
        file_path="auth/models.py",
        symbol_name="User",
        symbol_type="class",
        start_line=1,
        end_line=30,
        content="class User:\n    pass",
        token_count=15,
    )


@pytest.fixture
def compressed_context(snippet_a, snippet_b):
    return CompressedContext(
        snippets=[snippet_a, snippet_b],
        total_tokens=35,
        budget=4000,
        files_included=2,
        symbols_included=2,
    )


@pytest.fixture
def empty_context():
    return CompressedContext()


# ---------------------------------------------------------------------------
# format_task_section
# ---------------------------------------------------------------------------

class TestFormatTaskSection:
    def test_contains_task_header(self, full_ticket):
        result = format_task_section(full_ticket)
        assert result.startswith("## Task")

    def test_contains_title(self, full_ticket):
        result = format_task_section(full_ticket)
        assert "Add user authentication" in result

    def test_contains_description(self, full_ticket):
        result = format_task_section(full_ticket)
        assert "Implement JWT-based authentication for the API." in result

    def test_contains_acceptance_criteria_when_present(self, full_ticket):
        result = format_task_section(full_ticket)
        assert "acceptance criteria" in result.lower() or "Acceptance Criteria" in result
        assert "Users can log in" in result

    def test_omits_acceptance_criteria_when_empty(self, minimal_ticket):
        result = format_task_section(minimal_ticket)
        assert "Acceptance Criteria" not in result

    def test_contains_comments_when_present(self, full_ticket):
        result = format_task_section(full_ticket)
        assert "Consider using python-jose" in result
        assert "Check OWASP guidelines" in result

    def test_omits_comments_when_empty(self, minimal_ticket):
        result = format_task_section(minimal_ticket)
        assert "Comments" not in result

    def test_returns_string(self, full_ticket):
        assert isinstance(format_task_section(full_ticket), str)


# ---------------------------------------------------------------------------
# format_repo_context_section
# ---------------------------------------------------------------------------

class TestFormatRepoContextSection:
    def test_contains_header(self):
        result = format_repo_context_section("my-repo")
        assert "## Repository Context" in result

    def test_contains_repo_name(self):
        result = format_repo_context_section("my-repo")
        assert "my-repo" in result

    def test_different_repo_name(self):
        result = format_repo_context_section("awesome-service")
        assert "awesome-service" in result

    def test_returns_string(self):
        assert isinstance(format_repo_context_section("repo"), str)


# ---------------------------------------------------------------------------
# format_relevant_files_section
# ---------------------------------------------------------------------------

class TestFormatRelevantFilesSection:
    def test_contains_header(self):
        result = format_relevant_files_section(["auth/jwt.py"])
        assert "## Relevant Files" in result

    def test_lists_files_as_bullets(self):
        result = format_relevant_files_section(["auth/jwt.py", "auth/models.py"])
        assert "- auth/jwt.py" in result
        assert "- auth/models.py" in result

    def test_empty_list_shows_no_files_message(self):
        result = format_relevant_files_section([])
        assert "## Relevant Files" in result
        assert "No files identified" in result

    def test_single_file(self):
        result = format_relevant_files_section(["main.py"])
        assert "- main.py" in result

    def test_returns_string(self):
        assert isinstance(format_relevant_files_section([]), str)


# ---------------------------------------------------------------------------
# format_code_snippets_section
# ---------------------------------------------------------------------------

class TestFormatCodeSnippetsSection:
    def test_contains_header(self, snippet_a):
        result = format_code_snippets_section([snippet_a])
        assert "## Code Snippets" in result

    def test_contains_file_path(self, snippet_a):
        result = format_code_snippets_section([snippet_a])
        assert "auth/jwt.py" in result

    def test_contains_symbol_name_and_type(self, snippet_a):
        result = format_code_snippets_section([snippet_a])
        assert "create_token" in result
        assert "function" in result

    def test_contains_line_range(self, snippet_a):
        result = format_code_snippets_section([snippet_a])
        assert "10" in result
        assert "25" in result

    def test_content_in_code_block(self, snippet_a):
        result = format_code_snippets_section([snippet_a])
        assert "```" in result
        assert "def create_token" in result

    def test_multiple_snippets(self, snippet_a, snippet_b):
        result = format_code_snippets_section([snippet_a, snippet_b])
        assert "create_token" in result
        assert "User" in result

    def test_empty_list_shows_no_snippets_message(self):
        result = format_code_snippets_section([])
        assert "## Code Snippets" in result
        assert "No code snippets available" in result

    def test_returns_string(self, snippet_a):
        assert isinstance(format_code_snippets_section([snippet_a]), str)


# ---------------------------------------------------------------------------
# format_implementation_instructions_section
# ---------------------------------------------------------------------------

class TestFormatImplementationInstructionsSection:
    def test_contains_header(self, full_ticket):
        result = format_implementation_instructions_section(full_ticket)
        assert "## Implementation Instructions" in result

    def test_contains_make_changes_guideline(self, full_ticket):
        result = format_implementation_instructions_section(full_ticket)
        assert "Make changes to the files listed above" in result

    def test_contains_follow_patterns_guideline(self, full_ticket):
        result = format_implementation_instructions_section(full_ticket)
        assert "Follow existing code patterns" in result

    def test_contains_acceptance_criteria_guideline_when_present(self, full_ticket):
        result = format_implementation_instructions_section(full_ticket)
        assert "acceptance criteria" in result.lower()

    def test_omits_acceptance_criteria_guideline_when_empty(self, minimal_ticket):
        result = format_implementation_instructions_section(minimal_ticket)
        # Should not mention acceptance criteria when ticket has none
        assert "acceptance criteria" not in result.lower()

    def test_returns_string(self, full_ticket):
        assert isinstance(format_implementation_instructions_section(full_ticket), str)


# ---------------------------------------------------------------------------
# format_constraints_section
# ---------------------------------------------------------------------------

class TestFormatConstraintsSection:
    def test_contains_header(self):
        result = format_constraints_section()
        assert "## Constraints" in result

    def test_contains_minimize_changes(self):
        result = format_constraints_section()
        assert "Minimize changes to existing code" in result

    def test_contains_backward_compatibility(self):
        result = format_constraints_section()
        assert "Maintain backward compatibility" in result

    def test_contains_naming_conventions(self):
        result = format_constraints_section()
        assert "Follow existing naming conventions" in result

    def test_contains_error_handling(self):
        result = format_constraints_section()
        assert "Add appropriate error handling" in result

    def test_returns_string(self):
        assert isinstance(format_constraints_section(), str)


# ---------------------------------------------------------------------------
# format_expected_behavior_section
# ---------------------------------------------------------------------------

class TestFormatExpectedBehaviorSection:
    def test_contains_header(self, full_ticket):
        result = format_expected_behavior_section(full_ticket)
        assert "## Expected Behavior" in result

    def test_contains_ticket_title(self, full_ticket):
        result = format_expected_behavior_section(full_ticket)
        assert "Add user authentication" in result

    def test_contains_description_content(self, full_ticket):
        result = format_expected_behavior_section(full_ticket)
        assert "JWT-based authentication" in result

    def test_minimal_ticket(self, minimal_ticket):
        result = format_expected_behavior_section(minimal_ticket)
        assert "## Expected Behavior" in result
        assert "Fix null pointer bug" in result

    def test_returns_string(self, full_ticket):
        assert isinstance(format_expected_behavior_section(full_ticket), str)


# ---------------------------------------------------------------------------
# assemble_prompt
# ---------------------------------------------------------------------------

class TestAssemblePrompt:
    def test_contains_all_section_headers(self, full_ticket, compressed_context):
        result = assemble_prompt(full_ticket, compressed_context, "my-repo")
        assert "## Task" in result
        assert "## Repository Context" in result
        assert "## Relevant Files" in result
        assert "## Code Snippets" in result
        assert "## Implementation Instructions" in result
        assert "## Constraints" in result
        assert "## Expected Behavior" in result

    def test_extracts_unique_file_paths_from_snippets(self, full_ticket, compressed_context):
        result = assemble_prompt(full_ticket, compressed_context, "my-repo")
        assert "auth/jwt.py" in result
        assert "auth/models.py" in result

    def test_deduplicates_file_paths(self, full_ticket, snippet_a):
        # Two snippets from the same file
        duplicate_snippet = CodeSnippet(
            file_path="auth/jwt.py",
            symbol_name="verify_token",
            symbol_type="function",
            start_line=30,
            end_line=45,
            content="def verify_token(token: str) -> dict:\n    pass",
        )
        ctx = CompressedContext(snippets=[snippet_a, duplicate_snippet])
        result = assemble_prompt(full_ticket, ctx, "my-repo")
        # auth/jwt.py should appear in the relevant files list exactly once
        relevant_files_start = result.index("## Relevant Files")
        code_snippets_start = result.index("## Code Snippets")
        relevant_files_section = result[relevant_files_start:code_snippets_start]
        assert relevant_files_section.count("- auth/jwt.py") == 1

    def test_sections_joined_with_double_newlines(self, full_ticket, compressed_context):
        result = assemble_prompt(full_ticket, compressed_context, "my-repo")
        assert "\n\n" in result

    def test_empty_context_handled_gracefully(self, full_ticket, empty_context):
        result = assemble_prompt(full_ticket, empty_context, "my-repo")
        assert "No files identified" in result
        assert "No code snippets available" in result

    def test_returns_string(self, full_ticket, compressed_context):
        assert isinstance(assemble_prompt(full_ticket, compressed_context, "my-repo"), str)

    def test_repo_name_in_result(self, full_ticket, compressed_context):
        result = assemble_prompt(full_ticket, compressed_context, "my-repo")
        assert "my-repo" in result
