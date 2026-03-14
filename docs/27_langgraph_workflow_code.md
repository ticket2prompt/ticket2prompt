
# 27 LangGraph Workflow Code

Example LangGraph workflow for the retrieval pipeline.

```python
from langgraph.graph import StateGraph

def ticket_expansion(state):
    return state

def vector_search(state):
    return state

def ranking(state):
    return state

workflow = StateGraph()

workflow.add_node("expand", ticket_expansion)
workflow.add_node("vector_search", vector_search)
workflow.add_node("ranking", ranking)

workflow.add_edge("expand", "vector_search")
workflow.add_edge("vector_search", "ranking")

app = workflow.compile()
```
