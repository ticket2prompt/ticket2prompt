
# 20 Monorepo Indexing Strategy

This document defines how the system handles very large repositories (monorepos).
Many production repositories contain tens or hundreds of thousands of files,
multiple services, and multiple programming languages.

Naively indexing everything leads to slow indexing, huge vector stores,
and poor retrieval precision.

This document describes strategies to keep indexing and retrieval efficient.

---

# Monorepo Challenges

Large repositories often contain:

- multiple services
- shared libraries
- frontend and backend code
- infrastructure code
- generated code

Example layout:

services/
    payments/
    orders/
    checkout/

libs/
    auth/
    logging/

frontend/
    web/
    mobile/

Indexing everything as one codebase creates too much noise.

---

# Service-Level Indexing

Each service should be indexed separately.

Example:

services/payments → payments index
services/orders → orders index

Advantages:

- smaller vector collections
- faster retrieval
- more accurate context

---

# Module Detection

The system should attempt to detect modules automatically.

Signals:

- package.json
- go.mod
- pyproject.toml
- build.gradle
- service directories

Detected modules become indexing boundaries.

---

# Index Namespacing

Vector storage should include module metadata.

Example metadata:

repo: ecommerce-platform
module: payments
language: typescript

This allows retrieval queries to filter by module.

---

# Selective Indexing

Some directories should not be indexed.

Common exclusions:

node_modules
build
dist
coverage
generated code
vendor

This prevents vector database bloat.

---

# Incremental Indexing

Full re-indexing of large repositories is expensive.

Instead:

1. detect changed files via git diff
2. re-index only affected files
3. update graph edges
4. refresh embeddings

This dramatically reduces indexing time.

---

# Dependency Mapping

Even with module-level indexing, cross-service dependencies exist.

Example:

checkoutService → paymentService

The graph should capture these relationships across modules.

---

# Retrieval Scoping

When a Jira ticket references a specific service,
retrieval should prioritize that module.

Example:

Ticket: Retry payment gateway failures

Preferred scope:

services/payments

Fallback scope:

shared libraries

---

# Index Size Estimates

Typical monorepo:

100k files
400k symbols

After module separation:

payments module → 40k symbols
orders module → 30k symbols
shared libs → 50k symbols

This keeps vector collections manageable.

---

# Performance Targets

Indexing time target:

Initial indexing < 30 minutes

Incremental indexing < 2 minutes

---

# Storage Strategy

Vector DB collections:

payments_symbols
orders_symbols
shared_symbols

Graph tables include module identifiers.

---

# Future Improvements

Potential enhancements:

- dynamic service detection
- repository map generation
- service ownership inference

These improvements further improve retrieval accuracy.
