
# 16 Ticket Expansion & Multi-Query Retrieval

This document defines how Jira tickets are expanded before retrieval.
Jira tickets often contain vague or inconsistent wording compared to the
actual codebase terminology. Query expansion improves recall by generating
multiple related search queries.

---

# Problem

Developers frequently write tickets like:

"Fix PSP retry issue"

But the code may use different terminology:

paymentService
stripeGateway
chargeProcessor

Without expansion, vector search may miss relevant symbols.

---

# Goal

Transform a Jira ticket into multiple semantically related queries that
cover different terminology used in the codebase.

---

# Ticket Inputs

The system should extract text from:

- Ticket title
- Description
- Acceptance criteria
- Comments (optional)

Combined into a single retrieval input.

Example:

Title: Retry PSP failures
Description: Retry failed transactions when gateway returns error.

---

# Expansion Strategy

Use an LLM to generate related technical queries.

Example expansion output:

retry payment gateway
retry stripe failure
retry transaction charge
handle payment processing error
retry card payment

These queries represent different vocabulary that may exist in the repo.

---

# Multi‑Query Retrieval

Each generated query is embedded separately.

Pipeline:

ticket text
→ expansion
→ multiple queries
→ embedding generation
→ vector search for each query
→ merge results

This increases retrieval coverage.

---

# Query Limit

Recommended number of generated queries:

4 – 6

More queries increase recall but also increase latency.

---

# Deduplication

Search results from different queries may overlap.

Steps:

1. collect results from all queries
2. deduplicate symbols
3. aggregate scores

---

# Score Aggregation

If the same symbol appears across multiple queries,
increase its confidence score.

Example:

processPayment matched in 3 queries → boosted rank

---

# Latency Considerations

Multi‑query retrieval adds overhead.

Optimizations:

- batch vector searches
- cache ticket embeddings
- reuse expansion results

Target latency:

< 200 ms additional overhead.

---

# Failure Handling

If expansion fails:

fallback to:

single query embedding
keyword search
graph expansion

The system must still produce results.

---

# Integration with Retrieval Engine

Expanded queries feed directly into the hybrid retrieval engine.

Pipeline:

ticket
→ expansion
→ multi‑query embedding
→ vector search
→ keyword search
→ graph expansion
→ ranking
→ context builder
