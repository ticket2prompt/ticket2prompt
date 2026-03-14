"""Individual pipeline step functions.

Each step function takes a PipelineState dict and returns a partial dict
of state updates. External dependencies are injected via PipelineConfig.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypedDict

from prompts import CompressedContext, GeneratedPrompt
from prompts.context_compression import compress_context
from prompts.prompt_generator import generate_prompt
from retrieval import FileCandidate, SymbolMatch, TicketInput
from retrieval.graph_expansion import graph_expansion
from retrieval.keyword_search import keyword_search
from retrieval.ranking_engine import rank_files
from retrieval.ticket_expansion import expand_ticket
from retrieval.vector_search import embed_queries, merge_vector_results, search_single_query

logger = logging.getLogger(__name__)


class PipelineState(TypedDict, total=False):
    """Shared state flowing through the LangGraph pipeline."""

    # Inputs
    ticket: TicketInput
    repo: str

    # After expansion
    expanded_queries: List[str]

    # After embedding
    query_embeddings: List[List[float]]

    # After vector search
    vector_matches: List[SymbolMatch]

    # After keyword search
    keyword_matches: List[SymbolMatch]

    # After graph expansion
    graph_matches: List[SymbolMatch]

    # After ranking
    ranked_files: List[FileCandidate]

    # After compression
    compressed_context: CompressedContext
    file_contents: Dict[str, str]

    # After prompt generation
    generated_prompt: GeneratedPrompt

    # Error tracking
    errors: List[str]

    # Tenant context
    org_id: str
    project_id: str

    # Jira historical context
    similar_tickets: List[dict]


@dataclass
class PipelineConfig:
    """External dependencies and parameters for the pipeline."""

    postgres: Any
    qdrant: Any
    cache: Any = None
    llm_fn: Callable[[str], str] = field(default=lambda x: "")
    model_name: str = "all-MiniLM-L6-v2"
    top_k_per_query: int = 20
    max_queries: int = 6
    graph_max_depth: int = 2
    file_limit: int = 10
    token_budget: int = 5000
    jira_qdrant: Any = None  # QdrantVectorStore for Jira collection (optional)
    org_id: str = ""
    project_id: str = ""
    repo_base_path: str = ""  # on-disk root of the cloned repo


def build_steps(config: PipelineConfig) -> Dict[str, Callable]:
    """Build pipeline step functions with config injected via closure.

    Returns a dict mapping node names to step functions.
    """

    def intake_step(state: PipelineState) -> dict:
        """Validate ticket and initialize state."""
        ticket = state["ticket"]
        if not ticket.title or not ticket.title.strip():
            raise ValueError("Ticket title is required")
        return {"repo": ticket.repo, "errors": [], "org_id": config.org_id, "project_id": config.project_id}

    def jira_context_step(state: PipelineState) -> dict:
        """Search for similar historical Jira tickets."""
        if config.jira_qdrant is None:
            return {"similar_tickets": [], "org_id": config.org_id, "project_id": config.project_id}

        try:
            ticket = state["ticket"]
            query_text = f"jira ticket: {ticket.title}"
            embeddings = embed_queries([query_text], model_name=config.model_name)

            if not embeddings:
                return {"similar_tickets": [], "org_id": config.org_id, "project_id": config.project_id}

            # Search Jira collection, optionally filter by project_id
            filters = {"project_id": config.project_id} if config.project_id else None
            results = config.jira_qdrant.search(
                query_vector=embeddings[0],
                top_k=5,
                filters=filters,
            )

            similar = [
                {
                    "ticket_key": r["payload"].get("ticket_key", ""),
                    "title": r["payload"].get("title", ""),
                    "status": r["payload"].get("status", ""),
                    "score": r["score"],
                }
                for r in results
            ]

            # Deduplicate by ticket_key
            seen = set()
            deduped = []
            for t in similar:
                if t["ticket_key"] not in seen:
                    seen.add(t["ticket_key"])
                    deduped.append(t)

            return {"similar_tickets": deduped, "org_id": config.org_id, "project_id": config.project_id}
        except Exception as e:
            logger.warning("Jira context retrieval failed: %s", e)
            return {"similar_tickets": [], "org_id": config.org_id, "project_id": config.project_id}

    def expansion_step(state: PipelineState) -> dict:
        """Expand ticket into multiple search queries."""
        queries = expand_ticket(
            ticket=state["ticket"],
            llm_fn=config.llm_fn,
            cache=config.cache,
            max_queries=config.max_queries,
        )
        return {"expanded_queries": queries}

    def embedding_step(state: PipelineState) -> dict:
        """Embed expanded queries into vectors."""
        try:
            embeddings = embed_queries(
                state["expanded_queries"],
                model_name=config.model_name,
            )
            return {"query_embeddings": embeddings}
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            errors = list(state.get("errors", []))
            errors.append(f"Embedding failed: {e}")
            return {"query_embeddings": [], "errors": errors}

    def vector_search_step(state: PipelineState) -> dict:
        """Search Qdrant with each query embedding and merge results."""
        results_per_query = []
        for vec in state.get("query_embeddings", []):
            filters = {"repo": state["repo"]}
            if config.project_id:
                filters["project_id"] = config.project_id
            matches = search_single_query(
                config.qdrant,
                query_vector=vec,
                repo=state["repo"],
                top_k=config.top_k_per_query,
                filters=filters,
            )
            results_per_query.append(matches)
        merged = merge_vector_results(results_per_query)
        return {"vector_matches": merged}

    def keyword_search_step(state: PipelineState) -> dict:
        """Run keyword-based search."""
        matches = keyword_search(
            config.postgres,
            ticket=state["ticket"],
            repo=state["repo"],
            org_id=config.org_id,
            project_id=config.project_id,
        )
        return {"keyword_matches": matches}

    def graph_expansion_step(state: PipelineState) -> dict:
        """Expand matches through the code knowledge graph."""
        initial = list(state.get("vector_matches", [])) + list(
            state.get("keyword_matches", [])
        )
        try:
            expanded = graph_expansion(
                config.postgres,
                initial_matches=initial,
                max_depth=config.graph_max_depth,
                org_id=config.org_id,
                project_id=config.project_id,
            )
            return {"graph_matches": expanded}
        except Exception as e:
            logger.warning("Graph expansion failed: %s", e)
            errors = list(state.get("errors", []))
            errors.append(f"Graph expansion failed: {e}")
            return {"graph_matches": [], "errors": errors}

    def ranking_step(state: PipelineState) -> dict:
        """Rank files from all retrieval sources."""
        ranked = rank_files(
            vector_matches=state.get("vector_matches", []),
            keyword_matches=state.get("keyword_matches", []),
            graph_matches=state.get("graph_matches", []),
            postgres=config.postgres,
            repo=state["repo"],
            file_limit=config.file_limit,
            org_id=config.org_id,
            project_id=config.project_id,
        )
        return {"ranked_files": ranked}

    def compression_step(state: PipelineState) -> dict:
        """Load file contents and compress context to fit token budget."""
        file_contents: Dict[str, str] = {}
        for fc in state.get("ranked_files", []):
            path = fc.file_path
            if path not in file_contents and config.repo_base_path:
                full_path = os.path.join(config.repo_base_path, path)
                try:
                    with open(full_path, encoding="utf-8", errors="replace") as fh:
                        file_contents[path] = fh.read()
                except OSError:
                    logger.debug("Could not read file %s", full_path)

        compressed = compress_context(
            state.get("ranked_files", []),
            file_contents,
            token_budget=config.token_budget,
        )
        return {"compressed_context": compressed, "file_contents": file_contents}

    def prompt_step(state: PipelineState) -> dict:
        """Assemble final prompt from ticket and compressed context."""
        prompt = generate_prompt(
            ticket=state["ticket"],
            ranked_files=state.get("ranked_files", []),
            file_contents=state.get("file_contents", {}),
            token_budget=config.token_budget,
        )
        return {"generated_prompt": prompt}

    return {
        "intake": intake_step,
        "jira_context": jira_context_step,
        "expansion": expansion_step,
        "embedding": embedding_step,
        "vector_search": vector_search_step,
        "keyword_search": keyword_search_step,
        "graph_expansion": graph_expansion_step,
        "ranking": ranking_step,
        "compression": compression_step,
        "prompt": prompt_step,
    }
