
# 21 Incremental Indexing & Delta Updates

This document defines how the repository index stays up to date without
requiring full re-indexing of the entire codebase.

Large repositories change frequently. Rebuilding the entire index after every
commit would be too expensive. Instead, the system performs **incremental
indexing** based on Git changes.

---

# Goal

Ensure the code index, vector embeddings, and knowledge graph remain accurate
while minimizing compute cost and indexing time.

---

# Change Detection

Changes are detected using Git.

Sources of change events:

- new commits
- pull request merges
- branch updates
- webhook triggers from GitHub

Typical detection command:

git diff --name-only <previous_commit> <current_commit>

This returns the list of modified files.

---

# Changed File Classification

After detecting changed files, classify them into:

1. Modified files
2. Added files
3. Deleted files

Each type requires a different indexing action.

---

# Modified Files

For modified files:

1. remove previous symbols belonging to that file
2. re-run Tree-sitter parsing
3. extract updated symbols
4. regenerate embeddings
5. update graph edges

---

# Added Files

For newly added files:

1. parse file with Tree-sitter
2. extract symbols
3. generate embeddings
4. add graph edges
5. store metadata

---

# Deleted Files

When a file is removed:

1. delete symbols belonging to that file
2. remove embeddings from vector DB
3. delete graph edges referencing those symbols

---

# Embedding Refresh

Embeddings must be refreshed whenever symbol code changes.

Pipeline:

modified file
→ symbol extraction
→ embedding generation
→ vector update

Only affected vectors are updated.

---

# Graph Updates

Symbol relationships may change when code changes.

Steps:

1. remove edges related to modified symbols
2. recompute dependencies
3. insert updated graph edges

---

# Webhook Integration

GitHub webhooks can trigger indexing automatically.

Events used:

push
pull_request
merge

Webhook payload contains commit hashes needed for change detection.

---

# Batch Processing

Multiple file changes should be processed in batches.

Example:

commit modifies 20 files

Process:

1. collect all changed files
2. parse files concurrently
3. update embeddings in batches
4. update graph edges

Batching reduces indexing overhead.

---

# Conflict Handling

Sometimes indexing may run while another update occurs.

Strategies:

- use indexing locks
- queue updates using background workers
- ensure idempotent updates

---

# Performance Targets

Incremental indexing targets:

single file update → < 2 seconds
10 file update → < 10 seconds
50 file update → < 30 seconds

---

# Storage Updates

Systems affected by delta updates:

PostgreSQL

update symbol records
update graph edges

Vector database

update embeddings
delete removed symbols

Redis

invalidate cached retrieval results

---

# Fallback Strategy

If incremental indexing fails:

trigger full module re-index.

Full re-index should remain rare.

---

# Integration with Indexing Pipeline

Incremental indexing integrates with the repository indexing module.

Pipeline:

git change detection
→ file classification
→ symbol re-extraction
→ embedding update
→ graph update
→ cache invalidation
