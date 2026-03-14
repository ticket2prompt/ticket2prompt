# 10 Qdrant Vector Schema Design

This document defines how embeddings are stored in the Qdrant vector
database.

The vector store is used for semantic retrieval of code symbols when a
Jira ticket description is provided.

Qdrant stores embeddings for functions, classes, and modules rather than
entire files. This preserves code structure and improves retrieval
accuracy.

------------------------------------------------------------------------

# Why Symbol-Level Embeddings

Embedding entire files introduces noise and makes similarity search
unreliable.

Instead we embed:

-   Functions
-   Classes
-   Methods
-   Module summaries

This allows the retrieval engine to return precise code locations rather
than large files.

------------------------------------------------------------------------

# Qdrant Collection Design

Collection name:

code_symbols

Vector size depends on the embedding model used.

Example:

-   bge-small-en → 384
-   e5-base-v2 → 768

Distance metric:

cosine similarity

Example configuration:

{ "collection_name": "code_symbols", "vector_size": 384, "distance":
"Cosine" }

------------------------------------------------------------------------

# Stored Payload Fields

Each vector entry contains structured metadata in the payload.

Example payload:

{ "symbol_id": "sym_921", "symbol_name": "processPayment",
"symbol_type": "function", "file_path":
"src/services/paymentService.ts", "repo": "orders-service",
"start_line": 120, "end_line": 185, "module": "payments", "language":
"typescript" }

------------------------------------------------------------------------

# Example Vector Record

{ "id": "sym_921", "vector": \[0.12, 0.93, 0.44, ...\], "payload": {
"symbol_name": "processPayment", "symbol_type": "function", "file_path":
"src/services/paymentService.ts", "module": "payments" } }

------------------------------------------------------------------------

# Indexing Strategy

During repository indexing:

1.  Extract symbols using Tree-sitter
2.  Generate embeddings for symbol code blocks
3.  Insert vectors into Qdrant
4.  Store metadata in PostgreSQL

------------------------------------------------------------------------

# Search Query

When a Jira ticket arrives:

1.  Embed the ticket text
2.  Run vector search
3.  Retrieve top matching symbols

Example:

ticket embedding → Qdrant search

Results:

processPayment() handlePaymentError() retryPayment()

------------------------------------------------------------------------

# Aggregation Strategy

Multiple symbols may belong to the same file.

After retrieval:

1.  Group symbols by file
2.  Aggregate similarity scores
3.  Rank candidate files

Example:

paymentService.ts → score 2.1 retryHandler.ts → score 1.4

------------------------------------------------------------------------

# Filtering

Qdrant allows filtering on metadata fields.

Example filters:

repo = "orders-service" language = "typescript"

Example query:

search vectors where repo = target repository.

------------------------------------------------------------------------

# Recommended Index Size

Typical repository:

10k files 40k--120k symbols

Vector entries remain manageable for Qdrant.

------------------------------------------------------------------------

# Future Optimization

Possible improvements:

-   HNSW index tuning
-   per-language collections
-   module-based filtering
-   caching top results in Redis

------------------------------------------------------------------------

# Integration with Retrieval Engine

The vector search result becomes the first stage in the hybrid retrieval
pipeline.

Vector search → Graph expansion → Ranking → Context builder
