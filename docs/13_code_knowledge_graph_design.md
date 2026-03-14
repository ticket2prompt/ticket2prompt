# 13 Code Knowledge Graph Design

This document defines the design of the Code Knowledge Graph used in the
system.

The knowledge graph represents structural relationships between symbols
in the repository. While vector search provides semantic similarity, the
graph provides structural context.

Combining both allows the system to retrieve more accurate code context
for Jira tickets.

------------------------------------------------------------------------

# Purpose of the Code Graph

The code graph answers questions like:

-   Which functions call this function?
-   Which files depend on this module?
-   Which services are connected in a request flow?
-   Which code areas are impacted by a change?

This structural knowledge allows the retrieval engine to expand context
beyond the initial vector matches.

------------------------------------------------------------------------

# Graph Components

The graph consists of:

Nodes Edges

Nodes represent code symbols. Edges represent relationships between
symbols.

------------------------------------------------------------------------

# Node Types

Nodes correspond to symbols extracted during indexing.

Common node types:

function class method module interface struct

Example nodes:

PaymentService processPayment retryPayment StripeGateway

------------------------------------------------------------------------

# Edge Types

Edges represent relationships extracted from the AST.

Common edge types:

calls imports inherits implements references

Example:

retryPayment → processPayment (calls)

orderService → paymentService (imports)

------------------------------------------------------------------------

# Graph Storage

The graph is stored in PostgreSQL.

Two main tables:

symbols graph_edges

------------------------------------------------------------------------

# Symbols Table

Fields:

symbol_id symbol_name symbol_type file_path repo language start_line
end_line

------------------------------------------------------------------------

# Graph Edges Table

Fields:

from_symbol to_symbol relation_type

Example row:

from_symbol: retryPayment to_symbol: processPayment relation_type: calls

------------------------------------------------------------------------

# Graph Construction

Graph edges are created during the indexing stage.

Pipeline:

parse code → extract symbols → detect relationships → insert nodes →
insert edges

------------------------------------------------------------------------

# Graph Expansion During Retrieval

Vector search returns top matching symbols.

Example:

processPayment handlePaymentError

The graph then expands the neighborhood.

Example expansion:

processPayment → retryPayment → paymentController → stripeGateway

This expansion adds important context.

------------------------------------------------------------------------

# Depth Limits

Graph traversal depth must be limited.

Recommended depth:

1--2 hops

Example:

retryPayment → processPayment → stripeGateway

Deeper traversal may introduce noise.

------------------------------------------------------------------------

# Ranking Signals

Graph relationships influence retrieval ranking.

Signals:

distance from original symbol number of connections symbol centrality

Symbols closer to the original match receive higher priority.

------------------------------------------------------------------------

# Example Retrieval Flow

Step 1

Ticket: Add retry logic for payment gateway failures

Step 2

Vector search finds:

processPayment

Step 3

Graph expansion finds:

retryPayment stripeGateway paymentController

Step 4

Files associated with these symbols are selected for prompt generation.

------------------------------------------------------------------------

# Performance Optimization

Large repositories may contain 100k+ symbols.

Strategies:

index graph tables limit traversal depth cache frequent graph queries
use batch queries

------------------------------------------------------------------------

# Future Improvements

Potential upgrades:

graph databases (Neo4j) precomputed dependency clusters service-level
graphs

However PostgreSQL adjacency tables are sufficient for the initial
version.

------------------------------------------------------------------------

# Integration with Retrieval Engine

Final retrieval pipeline:

ticket → embedding search → symbol matches → graph expansion → ranking →
file selection → prompt generation
