
# 15 Ranking Algorithm Specification

This document defines how the retrieval engine ranks candidate files after
vector search, keyword search, and graph expansion.

Ranking is critical because the system may retrieve dozens of candidate
symbols but only a small number of files can fit into the final prompt.

The ranking engine determines which files are most relevant.

---

# Ranking Inputs

The ranking algorithm combines multiple signals:

1. Semantic similarity score
2. Graph proximity score
3. Keyword match score
4. Git recency score
5. Symbol density score

Each signal represents a different indicator of relevance.

---

# Semantic Similarity Score

This score comes directly from the vector database search results.

Higher similarity means the symbol meaning closely matches the Jira ticket.

Example:

processPayment → 0.89
retryPayment → 0.86

Semantic similarity is the strongest signal.

Recommended weight:

0.55

---

# Graph Proximity Score

This score measures how close a symbol is to the original match in the code graph.

Distance scoring:

distance 0 (direct match) → score 1.0
distance 1 (one hop) → score 0.7
distance 2 (two hops) → score 0.4

Graph traversal beyond depth 2 is discouraged due to noise.

Recommended weight:

0.20

---

# Keyword Match Score

Keyword search identifies files containing important ticket terms.

Example keywords:

payment
retry
gateway

Files containing multiple keyword matches receive higher scores.

Example scoring:

1 keyword match → 0.3
2 keyword matches → 0.6
3+ keyword matches → 1.0

Recommended weight:

0.15

---

# Git Recency Score

Files that changed recently are more likely to be relevant.

Signals used:

- last commit date
- commit frequency
- number of recent PRs touching the file

Example scoring:

modified in last 7 days → 1.0
modified in last 30 days → 0.7
older changes → 0.3

Recommended weight:

0.05

---

# Symbol Density Score

If multiple relevant symbols exist in the same file,
the file becomes more important.

Example:

paymentService.ts → 4 matching symbols
retryHandler.ts → 2 matching symbols

Density scoring:

1 symbol → 0.3
2 symbols → 0.6
3+ symbols → 1.0

Recommended weight:

0.05

---

# Final Ranking Formula

The final score is computed as:

final_score =
0.55 * semantic_similarity +
0.20 * graph_proximity +
0.15 * keyword_score +
0.05 * git_recency +
0.05 * symbol_density

Files are ranked in descending order.

---

# Example Ranking

Candidate files:

paymentService.ts
retryHandler.ts
stripeGateway.ts
paymentController.ts

Scores:

paymentService.ts → 0.92
retryHandler.ts → 0.84
stripeGateway.ts → 0.77
paymentController.ts → 0.63

Top files are selected for context building.

---

# Tie Breaking

When scores are similar:

Priority rules:

1. file with more symbol matches
2. file modified more recently
3. smaller file size

This reduces prompt noise.

---

# File Selection Limit

Final file count recommended:

8–12 files

Large files may be partially included during context compression.

---

# Score Normalization

All signals must be normalized to the range:

0 → 1

This prevents one signal from dominating the ranking.

---

# Performance Optimization

Ranking should execute within:

< 50 ms

Strategies:

- precompute graph distances
- cache recent commit metadata
- batch compute scores

---

# Output

The ranking engine outputs:

ranked_files
ranked_symbols

These are passed to the context builder and prompt generation modules.
