"""LangGraph pipeline orchestration.

Defines the StateGraph that wires together all pipeline steps
from ticket intake through prompt generation.
"""

from langgraph.graph import END, StateGraph

from retrieval import TicketInput
from workflows.pipeline_steps import PipelineConfig, PipelineState, build_steps


def build_pipeline(config: PipelineConfig):
    """Build and compile the LangGraph pipeline.

    Returns a compiled runnable with an .invoke() method.
    """
    steps = build_steps(config)

    workflow = StateGraph(PipelineState)

    workflow.add_node("intake", steps["intake"])
    workflow.add_node("jira_context", steps["jira_context"])
    workflow.add_node("expansion", steps["expansion"])
    workflow.add_node("embedding", steps["embedding"])
    workflow.add_node("vector_search", steps["vector_search"])
    workflow.add_node("keyword_search", steps["keyword_search"])
    workflow.add_node("graph_expansion", steps["graph_expansion"])
    workflow.add_node("ranking", steps["ranking"])
    workflow.add_node("compression", steps["compression"])
    workflow.add_node("prompt", steps["prompt"])

    workflow.set_entry_point("intake")

    workflow.add_edge("intake", "jira_context")
    workflow.add_edge("jira_context", "expansion")
    workflow.add_edge("expansion", "embedding")
    workflow.add_edge("embedding", "vector_search")
    workflow.add_edge("vector_search", "keyword_search")
    workflow.add_edge("keyword_search", "graph_expansion")
    workflow.add_edge("graph_expansion", "ranking")
    workflow.add_edge("ranking", "compression")
    workflow.add_edge("compression", "prompt")
    workflow.add_edge("prompt", END)

    return workflow.compile()


def run_pipeline(config: PipelineConfig, ticket: TicketInput) -> dict:
    """Run the full pipeline for a ticket and return the final state."""
    app = build_pipeline(config)
    return app.invoke({"ticket": ticket})
