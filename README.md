 # Ticket-to-Prompt: Jira → Context → Cursor

 Turn Jira tickets into high-quality, context-rich prompts for Cursor. This project does **not** generate code directly; instead, it builds precise prompts with the right repository context so you can safely implement changes in your editor.

 ---

 ## High-Level Pipeline

 The end-to-end flow from ticket to prompt:

 ```mermaid
 flowchart LR
   jira[JiraTicket] --> ticketIntake[TicketIntake]
   ticketIntake --> ticketExpansion[TicketExpansion]
   ticketExpansion --> embeddingGen[EmbeddingGeneration]
   embeddingGen --> vectorSearch[VectorSearch]
   vectorSearch --> graphExpansion[GraphExpansion]
   graphExpansion --> ranking[RankingEngine]
   ranking --> contextCompression[ContextCompression]
   contextCompression --> promptAssembly[PromptAssembly]
   promptAssembly --> cursorPrompt[CursorPrompt]
 ```

 Conceptually:

 1. **Jira Ticket** – Title, description, acceptance criteria, comments.
 2. **Ticket Expansion** – Expand into multiple technical queries.
 3. **Embedding + Vector Search** – Use open-source models + Qdrant over symbol embeddings.
 4. **Code Knowledge Graph Expansion** – Follow calls/imports/inheritance.
 5. **Ranking** – Combine semantic, structural, keyword, and git signals.
 6. **Context Compression** – Extract only relevant symbols/snippets.
 7. **Prompt Generation** – Build a structured Cursor prompt to guide implementation.

 See `docs/01_project_overview.md`, `docs/02_system_architecture.md`, and `docs/30_end_to_end_example_pipeline.md` for full specs.

 ---

 ## Architecture Overview

 The system is a Python backend that orchestrates indexing, retrieval, and prompt generation.

 ### Module Layout (Planned)

 ```mermaid
 flowchart TB
   apiMod[\"api/\nFastAPI endpoints\"] --> workflowsMod[\"workflows/\nLangGraph pipeline\"]
   workflowsMod --> retrievalMod[\"retrieval/\nvector + keyword + graph\"]
   workflowsMod --> promptsMod[\"prompts/\ncontext + prompt gen\"]
   workflowsMod --> indexingMod[\"indexing/\nindex + embeddings + graph\"]

   indexingMod --> storagePg[\"storage/postgres.py\"]
   indexingMod --> storageQdrant[\"storage/qdrant_client.py\"]
   indexingMod --> storageRedis[\"storage/redis_cache.py\"]

   retrievalMod --> storagePg
   retrievalMod --> storageQdrant
   retrievalMod --> storageRedis

   apiMod --> integrationsJira[\"integrations/jira_client.py\"]
   apiMod --> integrationsGithub[\"integrations/github_client.py\"]

   gitAnalysis[\"git_analysis/\nchange + commits\"] --> indexingMod
   gitAnalysis --> retrievalMod
 ```

 Planned directories (see `docs/09_repository_structure.md` and `docs/23_repository_scaffold.md`):

 - `api/` – FastAPI app and routes.
 - `indexing/` – Repository cloning, file filtering, symbol extraction, embeddings, graph building.
 - `retrieval/` – Vector/keyword search, graph expansion, ranking, context builder.
 - `prompts/` – Context compression and prompt templates/generation.
 - `workflows/` – LangGraph pipeline and pipeline steps.
 - `storage/` – PostgreSQL, Qdrant, Redis clients.
 - `integrations/` – Jira, GitHub, webhooks.
 - `git_analysis/` – Git change detection, incremental indexing.
 - `config/` – Settings and logging config.
 - `scripts/` – CLI utilities like `index_repository.py`.
 - `tests/` – Mirrors the main structure (`tests/indexing_tests/`, `tests/retrieval_tests/`, etc.).

 ---

 ## Tech Stack

 From `docs/03_open_source_stack.md` and related docs:

 - **Language**: Python 3.11+
 - **API Layer**: FastAPI
 - **Workflow Orchestration**: LangGraph
 - **LLM Abstraction**: LiteLLM (for ticket expansion and prompt optimization)
 - **Vector Database**: Qdrant (`code_symbols` collection, cosine distance, 384-dim embeddings)
 - **Metadata Store**: PostgreSQL (symbols, files, graph edges, git metadata)
 - **Cache Layer**: Redis
 - **Background Jobs**: Celery or Temporal (for indexing and heavy tasks)
 - **Code Parsing**: Tree-sitter (symbol extraction and dependency graph)
 - **Git Access**: GitPython
 - **Keyword Search**: ripgrep
 - **Embedding Models**: SentenceTransformers (`bge-small-en` as primary; `e5-base-v2` / `bge-base-en` as alternates)
 - **Containerization**: Docker, Docker Compose

 ---

 ## Local Development Setup

 This section mirrors `docs/29_local_development_setup.md`. It is aspirational until the code is implemented.

 1. **Prerequisites**
    - Python 3.11+
    - Docker and Docker Compose
    - Git

 2. **Clone the repository**

    ```bash
    git clone <this-repo-url> ticket-to-prompt
    cd ticket-to-prompt
    ```

 3. **Bring up infrastructure (Postgres, Redis, Qdrant)**

    Once `docker-compose.yml` exists:

    ```bash
    docker compose up -d
    ```

    Expected services (from `docs/29_local_development_setup.md`):
    - PostgreSQL (user `dev`, password `dev`, DB `code_context`, port `5432`)
    - Redis (port `6379`)
    - Qdrant (port `6333`)

 4. **Create and activate a virtual environment**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt  # or `pip install -e .` once pyproject.toml exists
    ```

 5. **Environment variables**

    Configure the following (e.g. in `.env`):

    ```bash
    POSTGRES_URL=postgresql://dev:dev@localhost:5432/code_context
    REDIS_URL=redis://localhost:6379
    QDRANT_URL=http://localhost:6333
    EMBEDDING_MODEL=bge-small-en
    ```

 6. **Run the API (after implementation)**

    ```bash
    uvicorn api.main:app --reload --port 8000
    ```

 7. **Index a repository (after indexing pipeline exists)**

    ```bash
    python scripts/index_repository.py --repo https://github.com/org/repo.git
    ```

 8. **Test a Jira ticket retrieval (after endpoints exist)**

    ```bash
    curl -X POST http://localhost:8000/jira/ticket \
      -H "Content-Type: application/json" \
      -d '{
        "ticket_id": "PAY-1234",
        "title": "Retry payment gateway failures",
        "description": "When Stripe returns a 5xx, retry the payment with exponential backoff."
      }'
    ```

## API Documentation

 Sphinx-based documentation is auto-generated from docstrings and the FastAPI OpenAPI spec.

 1. **Install docs dependencies**

    ```bash
    pip install -e ".[docs]"
    ```

 2. **Export the OpenAPI spec**

    ```bash
    python scripts/export_openapi.py
    ```

 3. **Build HTML documentation**

    ```bash
    cd docs/api-docs
    make html
    ```

 4. **View the output**

    Open `docs/api-docs/_build/html/index.html` in a browser.

 The documentation includes:
 - **REST API Reference** — auto-generated from the FastAPI OpenAPI spec via `sphinxcontrib-openapi`
 - **Python Module Reference** — auto-generated from source docstrings via `sphinx.ext.autodoc`

 ---

 ## Implementation Checklist (TDD-First)

 **Definition of Done applies to every item below**:

 - Write failing tests first.
 - Implement the code to make tests pass.
 - Only then mark both the **tests** and **implementation** checkboxes as done.

 The codebase is currently **empty** (no `api/`, `indexing/`, etc.). Use this checklist to drive implementation.

 ### Phase 1 — Project Foundation

- [x] **Repository scaffold and layout** (see `docs/09_repository_structure.md`, `docs/23_repository_scaffold.md`)
  - [x] Tests written (e.g. basic checks that key packages/imports exist)
  - [x] Implementation complete (`api/`, `indexing/`, `retrieval/`, `prompts/`, `workflows/`, `storage/`, `integrations/`, `git_analysis/`, `config/`, `scripts/`, `tests/` created)

 - [x] **Python dependency management** (see `docs/03_open_source_stack.md`, `docs/29_local_development_setup.md`)
   - [x] Tests written (e.g. smoke tests that dependencies import correctly)
   - [x] Implementation complete (`pyproject.toml` or `requirements.txt` with FastAPI, LangGraph, Qdrant client, PostgreSQL driver, Redis client, Tree-sitter, SentenceTransformers, etc.)

 - [x] **Docker Compose for infrastructure** (see `docs/29_local_development_setup.md`)
   - [x] Tests written (e.g. script that checks services are reachable on expected ports)
   - [x] Implementation complete (`docker-compose.yml` with Postgres, Redis, Qdrant)

 - [x] **Configuration module** (see `docs/03_open_source_stack.md`, `docs/29_local_development_setup.md`)
   - [x] Tests written (validate env parsing, defaults, and required settings)
   - [x] Implementation complete (`config/settings.py`, optional `config/logging_config.py`)

 - [x] **Database schema SQL & migrations** (see `docs/05_metadata_schema.md`, `docs/25_database_schema_sql.md`)
   - [x] Tests written (migrations apply cleanly; basic CRUD against `symbols`, `files`, `graph_edges`)
   - [x] Implementation complete (SQL or migration scripts that create core tables and indexes)

 ### Phase 2 — Repository Indexing

 - [x] **Repo cloner** (`indexing/repo_cloner.py`) (see `docs/04_repository_indexing.md`, `docs/24_python_module_skeletons.md`)
   - [x] Tests written (clone into temp dir; handle existing dirs; invalid URLs)
   - [x] Implementation complete (GitPython-based clone with proper error handling)

 - [x] **File filter** (`indexing/file_filter.py`) (see `docs/04_repository_indexing.md`, `docs/20_monorepo_indexing_strategy.md`)
   - [x] Tests written (filters out `node_modules/`, `dist/`, `build/`, `vendor/`, `coverage/`, generated code)
   - [x] Implementation complete (configurable ignore rules and language detection)

 - [x] **Tree-sitter parser & symbol extractor** (`indexing/symbol_extractor.py`) (see `docs/12_symbol_extraction_treesitter.md`)
   - [x] Tests written (for each supported language, extract correct symbols and locations)
   - [x] Implementation complete (AST traversal to collect functions, classes, methods, interfaces, structs, plus dependencies)

 - [x] **Embedding pipeline** (`indexing/embedding_pipeline.py`) (see `docs/11_embedding_strategy.md`)
   - [x] Tests written (batching, deterministic embeddings for known input, error cases)
   - [x] Implementation complete (batch symbol text formatting → embedding model → Qdrant insert)

 - [x] **Graph builder** (`indexing/graph_builder.py`) (see `docs/13_code_knowledge_graph_design.md`)
   - [x] Tests written (edges created correctly for calls/imports/inheritance/references)
   - [x] Implementation complete (populate `symbols` and `graph_edges` tables from symbol extraction output)

 ### Phase 3 — Storage Layer

 - [x] **PostgreSQL client** (`storage/postgres.py`) (see `docs/05_metadata_schema.md`, `docs/25_database_schema_sql.md`)
   - [x] Tests written (connection handling, basic queries, transaction behavior)
   - [x] Implementation complete (connection pool, simple CRUD helpers for symbols/files/graph_edges)

 - [x] **Qdrant client & collection setup** (`storage/qdrant_client.py`) (see `docs/10_qdrant_vector_schema.md`, `docs/26_qdrant_collection_setup.md`)
   - [x] Tests written (collection exists with correct schema; insert/search round-trip)
   - [x] Implementation complete (recreate/ensure `code_symbols` collection, helpers for upserts and search)

 - [x] **Redis cache** (`storage/redis_cache.py`) (see `docs/03_open_source_stack.md`)
   - [x] Tests written (set/get, TTL behavior, cache invalidation)
   - [x] Implementation complete (simple wrapper for caching embeddings, retrieval results, etc.)

 ### Phase 4 — Retrieval Pipeline

 - [x] **Ticket expansion / multi-query** (`retrieval/ticket_expansion.py`) (see `docs/16_ticket_expansion_multiquery.md`)
   - [x] Tests written (number and quality of expansions; fallbacks when LLM unavailable)
   - [x] Implementation complete (LLM-based or heuristic expansion to 4–6 queries per ticket)

 - [x] **Vector search** (`retrieval/vector_search.py`) (see `docs/10_qdrant_vector_schema.md`, `docs/14_hybrid_retrieval_engine.md`, `docs/24_python_module_skeletons.md`)
   - [x] Tests written (search against a small fixture collection, deterministic ordering)
   - [x] Implementation complete (embedding query text, calling Qdrant, returning top symbols)

 - [x] **Keyword search** (`retrieval/keyword_search.py`) (see `docs/14_hybrid_retrieval_engine.md`)
   - [x] Tests written (correct files returned for keyword queries; respects ignore rules)
   - [x] Implementation complete (ripgrep-based search over working copy)

 - [x] **Graph expansion** (`retrieval/graph_expansion.py`) (see `docs/13_code_knowledge_graph_design.md`, `docs/14_hybrid_retrieval_engine.md`)
   - [x] Tests written (1–2 hop expansion; correct relation filtering and depth limits)
   - [x] Implementation complete (retrieve neighbors from `graph_edges`, compute proximity scores)

 - [x] **Ranking engine** (`retrieval/ranking_engine.py`) (see `docs/15_ranking_algorithm_spec.md`, `docs/14_hybrid_retrieval_engine.md`)
   - [x] Tests written (scoring formula correctness, tie-breaking, Top-K selection)
   - [x] Implementation complete (combine semantic similarity, graph proximity, keyword score, git recency, symbol density)

 ### Phase 5 — Prompt Generation

 - [x] **Context compression** (`prompts/context_compression.py`) (see `docs/17_context_compression_system.md`)
   - [x] Tests written (token budgeting, snippet extraction, deduplication, ordering)
   - [x] Implementation complete (select ranked symbols/snippets under 4000–6000 token budget)

 - [x] **Prompt templates** (`prompts/prompt_templates.py`) (see `docs/07_prompt_generation.md`, `docs/18_cursor_prompt_optimization.md`)
   - [x] Tests written (all required sections present, template variables filled)
   - [x] Implementation complete (structured templates for task summary, context, files, snippets, instructions, constraints, expected behavior)

 - [x] **Prompt generator** (`prompts/prompt_generator.py`) (see `docs/07_prompt_generation.md`, `docs/18_cursor_prompt_optimization.md`, `docs/24_python_module_skeletons.md`)
   - [x] Tests written (given a synthetic retrieval result, output is well-formed and coherent)
   - [x] Implementation complete (assemble final prompt string from compressed context and templates)

 ### Phase 6 — Workflow Orchestration

 - [x] **LangGraph pipeline** (`workflows/langgraph_pipeline.py`) (see `docs/19_langgraph_workflow_design.md`, `docs/27_langgraph_workflow_code.md`)
   - [x] Tests written (graph compiles; basic state flows through nodes as expected)
   - [x] Implementation complete (`StateGraph` defining nodes: intake, expansion, embedding, vector search, keyword search, graph expansion, ranking, compression, prompt)

 - [x] **Pipeline steps & shared state** (`workflows/pipeline_steps.py`) (see `docs/19_langgraph_workflow_design.md`)
   - [x] Tests written (each node function reads/writes expected state keys; error paths)
   - [x] Implementation complete (state dataclass and distinct step functions wired into LangGraph)

 ### Phase 7 — API Layer

 - [x] **FastAPI application** (`api/main.py`) (see `docs/28_fastapi_endpoints.md`)
   - [x] Tests written (health check, OpenAPI schema, basic startup)
   - [x] Implementation complete (FastAPI app instance, middleware, dependency injection wiring)

 - [x] **Jira ticket endpoint** (`POST /jira/ticket`) (see `docs/28_fastapi_endpoints.md`)
   - [x] Tests written (valid/invalid payloads; end-to-end pipeline stub)
   - [x] Implementation complete (accept ticket payload, trigger LangGraph workflow, return ticket/prompt ID)

 - [x] **Repository indexing endpoint** (`POST /repo/index`) (see `docs/28_fastapi_endpoints.md`)
   - [x] Tests written (valid/invalid repo URLs; background job triggering)
   - [x] Implementation complete (start indexing job and return status)

 - [x] **Prompt retrieval endpoint** (`GET /prompt/{ticket_id}`) (see `docs/28_fastapi_endpoints.md`)
   - [x] Tests written (existing vs missing ticket IDs)
   - [x] Implementation complete (fetch final prompt from storage or cache)

 ### Phase 8 — Integrations and Operations

 - [x] **Jira client** (`integrations/jira_client.py`) (see `docs/02_system_architecture.md`)
   - [x] Tests written (API token handling, pagination, error cases)
   - [x] Implementation complete (fetch ticket metadata and comments)

 - [x] **GitHub client** (`integrations/github_client.py`) (see `docs/02_system_architecture.md`)
   - [x] Tests written (repo metadata, PR data, rate limit handling)
   - [x] Implementation complete (basic interactions needed for indexing and git deltas)

 - [x] **Git change detector** (`git_analysis/change_detector.py`) (see `docs/21_incremental_indexing_delta_updates.md`)
   - [x] Tests written (`git diff` parsing; classification into added/modified/deleted)
   - [x] Implementation complete (compute file deltas between commits/branches)

 - [x] **Incremental indexing logic** (`git_analysis/commit_analyzer.py`) (see `docs/21_incremental_indexing_delta_updates.md`)
   - [x] Tests written (only changed symbols re-indexed; idempotency)
   - [x] Implementation complete (drive partial re-index updates for symbols, embeddings, graph edges)

 - [x] **Indexing script** (`scripts/index_repository.py`) (see `docs/23_repository_scaffold.md`, `docs/29_local_development_setup.md`)
   - [x] Tests written (CLI argument parsing; dry-run mode)
   - [x] Implementation complete (script to clone + index a repo end-to-end)

 ### Phase 9 — Evaluation and Quality

 - [x] **Retrieval metrics implementation** (see `docs/22_evaluation_retrieval_metrics.md`)
   - [x] Tests written (precision/recall/Top-K computation on fixtures)
   - [x] Implementation complete (utility to compute metrics for a test ticket set)

 - [x] **Evaluation dataset** (see `docs/22_evaluation_retrieval_metrics.md`)
   - [x] Tests written (data loader integrity checks)
   - [x] Implementation complete (50–200 curated tickets with expected files/symbols/behaviors)

 - [x] **End-to-end pipeline test** (see `docs/30_end_to_end_example_pipeline.md`)
   - [x] Tests written (E2E test that goes from synthetic ticket → prompt)
   - [x] Implementation complete (glue code + fixtures to drive the full pipeline)

 ### Phase 10 — Monorepo and Advanced Features

 - [x] **Monorepo indexing strategy** (see `docs/20_monorepo_indexing_strategy.md`)
   - [x] Tests written (indexing scoped to modules/services; cross-service dependencies detected)
   - [x] Implementation complete (module detection and per-module indices/collections)

 - [x] **Service-level index namespacing** (see `docs/20_monorepo_indexing_strategy.md`)
   - [x] Tests written (retrieval scoped by service name/module)
   - [x] Implementation complete (store `repo`/`module` metadata and route retrieval accordingly)

 - [x] **Webhook handlers** (`integrations/webhook_handlers.py`) (see `docs/21_incremental_indexing_delta_updates.md`)
   - [x] Tests written (GitHub webhook payloads; security validations)
   - [x] Implementation complete (webhooks to trigger incremental indexing on pushes/merges)

### Phase 11 — Production Readiness

- [x] **Webhook-to-indexing wiring** (`integrations/webhook_handlers.py` → `indexing/incremental_service.py`)
  - [x] Tests written (webhook dispatch triggers incremental service; Redis-unavailable fallback; no-changes early exit)
  - [x] Implementation complete (webhooks dispatch `CommitAnalyzer.process_changes()` via Celery tasks for push and merged-PR events)

- [x] **Background job infrastructure** (`workers/celery_app.py`, `workers/tasks.py`)
  - [x] Tests written (task success paths, cleanup verification, cache status updates, retry behavior)
  - [x] Implementation complete (Celery with Redis broker; `index_repository_full` and `index_repository_incremental` tasks with retries; API endpoints dispatch via `.delay()`)

- [x] **MonorepoIndexer integration** (`scripts/index_repository.py`, `api/routes/repo_routes.py`)
  - [x] Tests written (CLI delegates to MonorepoIndexer; API endpoint runs full indexing with MonorepoIndexer)
  - [x] Implementation complete (`run_full_index` delegates to `MonorepoIndexer.index_repository()`; API endpoint clones, cleans, and indexes via MonorepoIndexer)

- [x] **Integration tests with live infrastructure** (`tests/live_infra_tests/`)
  - [x] Tests written (23 tests: PostgresClient CRUD, QdrantVectorStore upsert/search/delete, RedisCache operations, E2E index-and-search pipeline)
  - [x] Implementation complete (testcontainers-python fixtures for Postgres, Qdrant, Redis; session-scoped containers; schema auto-applied)

- [x] **Docker Compose full deployment** (`Dockerfile`, `docker-compose.yml`)
  - [x] Tests written (5-service validation, health checks, depends_on conditions, schema mount, environment variables)
  - [x] Implementation complete (Dockerfile with Python 3.13-slim; `app` and `celery-worker` services; health checks on all infra; schema.sql auto-init; `.env.example` for onboarding)

 ---

 ## Definition of Done (Project-Wide)

 This project uses a **tests-first definition of done**:

 - For every checklist item above:
   - **Tests are written first** and must fail initially.
   - The implementation is written **only to the extent needed** to make those tests pass.
   - All relevant tests (unit + integration/E2E where applicable) must be green in CI.
 - Only after the above is satisfied should you:
   - Mark **“Tests written”** as `[ ]`.
   - Mark **“Implementation complete”** as `[ ]`.
   - Optionally mark the parent item checkbox as `[ ]` once all its sub-items are done.

 Avoid skipping tests or retrofitting them after the fact; this README is intended to enforce the TDD flow described in `.cursor/rules/buildingrules.mdc`.

 ---

 ## Documentation Reference Table

 Quick reference mapping design docs to implementation phases:

 | Doc | Title | Primary Topics | Phases |
 | --- | ----- | -------------- | ------ |
 | 01 | Project Overview | High-level goals & principles | All |
 | 02 | System Architecture | Pipeline & core modules | 1–8 |
 | 03 | Open Source Stack | Tech choices | 1, 2, 3, 4, 5, 7, 8 |
 | 04 | Repository Indexing | Indexing pipeline | 2, 3 |
 | 05 | Metadata Schema | Symbols/files/graph tables | 1, 2, 3 |
 | 06 | Retrieval Pipeline | End-to-end retrieval stages | 4 |
 | 07 | Prompt Generation | Prompt sections & structure | 5 |
 | 08 | Build Roadmap | 6-week MVP plan | All |
 | 09 | Repository Structure | Directory layout | 1 |
 | 10 | Qdrant Vector Schema | Collection & payload design | 2, 3, 4 |
 | 11 | Embedding Strategy | Code & ticket embeddings | 2, 4 |
 | 12 | Symbol Extraction (Tree-sitter) | AST parsing and symbols | 2 |
 | 13 | Code Knowledge Graph Design | Graph nodes/edges & traversal | 2, 4 |
 | 14 | Hybrid Retrieval Engine | Semantic + keyword + graph | 4 |
 | 15 | Ranking Algorithm Spec | Scoring formula & weights | 4 |
 | 16 | Ticket Expansion & Multi-Query | Expanding tickets into multiple queries | 4 |
 | 17 | Context Compression System | Snippet extraction & token budgeting | 5 |
 | 18 | Cursor Prompt Optimization | Final prompt shaping | 5 |
 | 19 | LangGraph Workflow Design | Pipeline orchestration | 6 |
 | 20 | Monorepo Indexing Strategy | Service-level indexing & scoping | 2, 10 |
 | 21 | Incremental Indexing & Delta Updates | Git-based incremental updates | 2, 8, 10 |
 | 22 | Evaluation & Retrieval Metrics | Precision/recall/Top-K evaluation | 9 |
 | 23 | Repository Scaffold | Base layout & scripts | 1, 2, 8 |
 | 24 | Python Module Skeletons | Key module signatures | 2, 4, 5 |
 | 25 | Database Schema SQL | Concrete SQL definitions | 1, 3 |
 | 26 | Qdrant Collection Setup | Code for Qdrant config | 3, 4 |
 | 27 | LangGraph Workflow Code | Example workflow code | 6 |
 | 28 | FastAPI Endpoints | API surface | 7 |
 | 29 | Local Development Setup | Dev environment & commands | 1, 3, 7, 8 |
 | 30 | End-to-End Example Pipeline | Worked example from ticket to prompt | 4, 5, 6, 9 |

 Use this table to jump from a checklist item back to its authoritative design document while you implement the system.

