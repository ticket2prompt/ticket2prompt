
# 19 LangGraph Workflow Design

This document defines the orchestration workflow for the Jira → Context → Cursor
prompt system using LangGraph.

LangGraph is used to model the system as a directed workflow graph where each
node represents a processing stage and edges represent data flow between stages.

---

# Workflow Goals

The workflow must:

- coordinate the full pipeline from Jira ticket to final prompt
- allow retries when failures occur
- maintain state between stages
- support asynchronous indexing and retrieval
- remain modular so stages can evolve independently

---

# Workflow Stages

The main stages are:

1. Ticket Intake
2. Ticket Expansion
3. Embedding Generation
4. Vector Search
5. Keyword Search
6. Graph Expansion
7. Ranking
8. Context Compression
9. Prompt Assembly
10. Prompt Delivery

Each stage becomes a node in the LangGraph workflow.

---

# Graph Overview

Jira Ticket
↓
Ticket Expansion
↓
Embedding Generation
↓
Vector Search
↓
Keyword Search
↓
Graph Expansion
↓
Ranking Engine
↓
Context Compression
↓
Prompt Generator
↓
Prompt Output

---

# State Object

LangGraph maintains a shared state object passed between nodes.

Example state fields:

ticket_text
expanded_queries
embeddings
retrieved_symbols
candidate_files
ranked_files
compressed_context
final_prompt

Each node reads and writes to this shared state.

---

# Node Responsibilities

Ticket Intake Node

Receives the Jira ticket and prepares the initial state.

Ticket Expansion Node

Generates multiple retrieval queries using the expansion strategy.

Embedding Node

Creates embeddings for each expanded query.

Vector Search Node

Queries the vector database to retrieve matching symbols.

Keyword Search Node

Runs lexical search across repository files.

Graph Expansion Node

Expands retrieved symbols through the code knowledge graph.

Ranking Node

Ranks candidate files using the ranking algorithm.

Context Compression Node

Extracts relevant snippets and compresses context.

Prompt Generator Node

Builds the final Cursor prompt.

Prompt Delivery Node

Returns the prompt to the user or IDE integration.

---

# Retry Strategy

Failures can occur at several stages.

Retry rules:

embedding generation → retry once
vector search → retry once
graph expansion → fallback to vector results
context compression → skip low-priority files

---

# Parallelization

Certain stages can run in parallel.

Vector search and keyword search may execute concurrently.

Results are merged before ranking.

---

# Error Handling

The workflow must handle:

- missing repository index
- failed embedding generation
- empty vector results

Fallback strategies:

- trigger repository re-indexing
- increase keyword search weight
- expand graph traversal depth

---

# Observability

Each workflow stage should log:

execution time
input size
output size

Metrics help identify performance bottlenecks.

---

# Performance Targets

Total workflow latency target:

< 2 seconds

Typical breakdown:

ticket expansion → 200 ms
vector search → 150 ms
graph expansion → 100 ms
ranking → 50 ms
compression → 200 ms
prompt assembly → 50 ms

---

# Future Enhancements

Possible improvements:

- agent-based workflow decisions
- adaptive retrieval strategies
- caching retrieval results
- streaming partial results

---

# Integration with API Layer

The FastAPI backend triggers the workflow when a Jira ticket is received.

API → LangGraph Workflow → Prompt Output
