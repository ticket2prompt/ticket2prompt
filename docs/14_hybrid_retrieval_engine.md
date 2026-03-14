
# 14 Hybrid Retrieval Engine

This document defines the hybrid retrieval engine that combines multiple search
signals to identify the most relevant files for a Jira ticket.

Relying only on vector similarity is insufficient for codebases. The system must
combine semantic search, keyword search, and structural graph traversal.

---

# Retrieval Objectives

The retrieval system must:

- identify relevant code symbols from vague Jira tickets
- tolerate different vocabulary between tickets and code
- include structurally related files
- rank files by likelihood of relevance

---

# Retrieval Signals

The system combines three signals:

1. Semantic similarity (vector search)
2. Keyword relevance (text search)
3. Structural proximity (code graph)

Each signal captures different information.

---

# Stage 1 – Query Expansion

Before retrieval begins, the system expands the ticket description into
multiple related queries.

Example ticket:

Add retry for PSP failures

Expanded queries:

retry payment gateway
retry stripe failures
handle payment error retry
retry transaction processing

Each query is embedded separately.

---

# Stage 2 – Vector Search

For each expanded query:

1. generate embedding
2. search vectors in Qdrant
3. retrieve top symbols

Example results:

processPayment
retryPayment
handlePaymentError

These represent semantically similar code.

---

# Stage 3 – Keyword Search

Keyword search provides lexical matches when vector similarity fails.

Tool used:

ripgrep

Example:

search terms:

payment
retry
gateway

Keyword matches may reveal files missed by vector search.

---

# Stage 4 – Graph Expansion

After initial matches, the system expands through the knowledge graph.

Example:

processPayment → stripeGateway
processPayment → paymentController

Traversal depth:

1–2 hops

This ensures contextual files are included.

---

# Stage 5 – Symbol Aggregation

Symbols returned from all stages are grouped by file.

Example:

paymentService.ts → 3 matches
retryHandler.ts → 2 matches
stripeGateway.ts → 1 match

Scores are aggregated per file.

---

# Stage 6 – Ranking

Each file receives a final score based on multiple signals.

Example scoring formula:

final_score =
0.55 * semantic_similarity +
0.25 * graph_proximity +
0.20 * keyword_score

Files are ranked in descending order.

---

# Stage 7 – File Selection

The retrieval engine returns the top candidate files.

Recommended limit:

8–12 files

Too few files risks missing context.
Too many files exceed prompt limits.

---

# Example End-to-End Retrieval

Ticket:

Add retry logic for payment gateway failures.

Vector matches:

processPayment
handlePaymentError

Graph expansion:

retryPayment
stripeGateway

Keyword matches:

paymentController

Final file selection:

paymentService.ts
retryHandler.ts
stripeGateway.ts
paymentController.ts

---

# Failure Handling

Sometimes vector search fails due to poor ticket wording.

Fallback strategies:

increase keyword weighting
increase graph expansion
run additional query expansions

---

# Performance Considerations

Typical retrieval latency target:

< 500 ms

Strategies:

cache embeddings
limit graph depth
batch vector searches

---

# Integration with Prompt Builder

The retrieval engine outputs:

relevant_files
relevant_symbols

These inputs feed the prompt generation system.
