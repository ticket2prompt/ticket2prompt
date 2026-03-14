
# 09 Repository Structure and Module Layout

This document defines the recommended repository structure for the Jira → Context → Cursor Prompt system.

The goal is to keep the system modular so that indexing, retrieval, and prompt generation can evolve independently.

---

# Root Repository Structure

```
jira-cursor-context/
│
├── api/
│   ├── main.py
│   ├── routes/
│   ├── schemas/
│   └── dependencies/
│
├── indexing/
│   ├── repo_cloner.py
│   ├── file_filter.py
│   ├── tree_sitter_parser.py
│   ├── symbol_extractor.py
│   ├── embedding_pipeline.py
│   └── graph_builder.py
│
├── retrieval/
│   ├── vector_search.py
│   ├── keyword_search.py
│   ├── graph_expansion.py
│   ├── ranking_engine.py
│   └── context_builder.py
│
├── prompts/
│   ├── prompt_generator.py
│   ├── prompt_templates.py
│   └── context_compression.py
│
├── integrations/
│   ├── jira_client.py
│   ├── github_client.py
│   └── webhook_handlers.py
│
├── git_analysis/
│   ├── commit_analyzer.py
│   ├── change_detector.py
│   └── ownership_mapper.py
│
├── storage/
│   ├── postgres.py
│   ├── qdrant_client.py
│   └── redis_cache.py
│
├── workflows/
│   ├── langgraph_pipeline.py
│   └── pipeline_steps.py
│
├── config/
│   ├── settings.py
│   └── logging_config.py
│
├── scripts/
│   ├── index_repository.py
│   └── reindex_changed_files.py
│
└── tests/
    ├── indexing_tests/
    ├── retrieval_tests/
    └── prompt_tests/
```

---

# Module Responsibilities

## API Layer

Directory:
```
api/
```

Responsibilities:

- HTTP endpoints
- webhook receivers
- authentication
- orchestration triggers

Example endpoints:

```
POST /jira/ticket
POST /repo/index
GET /prompt/{ticket_id}
```

---

# Indexing Module

Directory:

```
indexing/
```

Responsibilities:

- clone repositories
- parse source code
- extract symbols
- generate embeddings
- build dependency graphs

Key files:

```
repo_cloner.py
symbol_extractor.py
graph_builder.py
embedding_pipeline.py
```

---

# Retrieval Engine

Directory:

```
retrieval/
```

Responsibilities:

- semantic search
- keyword search
- dependency expansion
- ranking relevant files

Modules:

```
vector_search.py
keyword_search.py
graph_expansion.py
ranking_engine.py
```

---

# Prompt Engine

Directory:

```
prompts/
```

Responsibilities:

- prompt templates
- context compression
- final prompt assembly

Modules:

```
prompt_generator.py
context_compression.py
```

---

# Integrations

Directory:

```
integrations/
```

Responsibilities:

- Jira API
- GitHub API
- webhook listeners

Files:

```
jira_client.py
github_client.py
webhook_handlers.py
```

---

# Git Analysis

Directory:

```
git_analysis/
```

Responsibilities:

- commit analysis
- recent file changes
- developer ownership

Modules:

```
commit_analyzer.py
change_detector.py
ownership_mapper.py
```

---

# Storage Layer

Directory:

```
storage/
```

Responsibilities:

- PostgreSQL access
- Qdrant vector storage
- Redis caching

Files:

```
postgres.py
qdrant_client.py
redis_cache.py
```

---

# Workflow Orchestration

Directory:

```
workflows/
```

Responsibilities:

- orchestration of the full pipeline
- step coordination

Uses:

LangGraph

Main file:

```
langgraph_pipeline.py
```

---

# Testing Strategy

Directory:

```
tests/
```

Test areas:

- indexing accuracy
- retrieval precision
- prompt correctness
- ranking quality
