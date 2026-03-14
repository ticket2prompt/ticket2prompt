# 11 Embedding Strategy

This document defines how embeddings are generated for both Jira tickets
and repository code symbols. The embedding layer is critical because
retrieval quality depends heavily on semantic representation.

All models selected must be open-source and runnable locally.

------------------------------------------------------------------------

# Embedding Objectives

The embedding system must:

-   capture semantic meaning of code
-   support natural language queries from Jira tickets
-   work across multiple programming languages
-   be efficient enough for large repositories
-   remain fully open source

------------------------------------------------------------------------

# Recommended Models

Primary model:

bge-small-en

Vector size: 384

Advantages:

-   strong semantic search performance
-   lightweight and fast
-   open source

Alternative models:

e5-base-v2 bge-base-en

These provide higher quality embeddings but require more compute.

------------------------------------------------------------------------

# Code Embedding Strategy

Embeddings are generated at the symbol level.

Symbols include:

-   functions
-   classes
-   methods
-   module summaries

Example embedding input:

Function: processPayment

Description: Handles payment processing including retry logic and
gateway interaction.

Code: `<function body>`{=html}

Combining description + code improves retrieval quality.

------------------------------------------------------------------------

# Ticket Embedding Strategy

When a Jira ticket arrives:

1.  Extract title
2.  Extract description
3.  Combine acceptance criteria
4.  Include discussion comments

Construct embedding input:

Title + Description + Acceptance Criteria

Example:

Add retry logic for payment gateway failures when Stripe API returns
500.

Embed this combined text.

------------------------------------------------------------------------

# Query Expansion

Tickets may contain vague wording.

Before embedding, generate expanded queries.

Example:

Original ticket:

Retry PSP failure

Expanded queries:

retry payment gateway retry stripe failure retry payment transaction
handle payment error

Each query is embedded separately.

------------------------------------------------------------------------

# Multi-Query Retrieval

For each expanded query:

1.  Generate embedding
2.  Run vector search
3.  Merge results

This improves recall when wording differs between code and tickets.

------------------------------------------------------------------------

# Normalization

Normalize embeddings before storage and search.

Steps:

1.  remove extra whitespace
2.  normalize casing
3.  truncate extremely long code blocks
4.  remove comments where appropriate

------------------------------------------------------------------------

# Batch Embedding Pipeline

When indexing a repository:

1.  collect extracted symbols
2.  batch symbols (50--200 per batch)
3.  generate embeddings
4.  insert vectors into Qdrant

Batching significantly improves indexing speed.

------------------------------------------------------------------------

# Embedding Refresh Strategy

Embeddings must update when code changes.

Trigger refresh when:

-   file changes
-   new commit modifies symbol
-   repository re-indexing occurs

Incremental updates are preferred over full re-indexing.

------------------------------------------------------------------------

# Storage Integration

Embeddings are stored in Qdrant.

Metadata is stored in PostgreSQL.

Mapping:

symbol_id → vector_id

This allows retrieval results to resolve quickly to actual code
locations.

------------------------------------------------------------------------

# Performance Considerations

Typical repository:

10k files 50k symbols

Embedding cost remains manageable with local models.

------------------------------------------------------------------------

# Future Improvements

Possible enhancements:

-   code-aware embeddings
-   cross-language embeddings
-   fine-tuned embeddings on repository data

These improvements can significantly boost retrieval accuracy.
