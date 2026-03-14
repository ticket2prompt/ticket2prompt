
# 23 Repository Scaffold

Recommended repository layout for the full system.

```
jira-cursor-context/
│
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── jira_routes.py
│   │   ├── repo_routes.py
│   │   └── prompt_routes.py
│   └── schemas/
│
├── indexing/
│   ├── repo_cloner.py
│   ├── file_filter.py
│   ├── symbol_extractor.py
│   ├── embedding_pipeline.py
│   └── graph_builder.py
│
├── retrieval/
│   ├── vector_search.py
│   ├── keyword_search.py
│   ├── graph_expansion.py
│   └── ranking_engine.py
│
├── prompts/
│   ├── context_compression.py
│   └── prompt_generator.py
│
├── workflows/
│   └── langgraph_pipeline.py
│
├── storage/
│   ├── postgres.py
│   ├── qdrant_client.py
│   └── redis_cache.py
│
├── git_analysis/
│   └── change_detector.py
│
├── config/
│   └── settings.py
│
├── scripts/
│   └── index_repository.py
│
└── tests/
    └── retrieval_tests/
```
