## Workflow Orchestration
 
### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity
 
### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution
 
### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project
 
### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness
 
### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it
 
### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how
 
## Task Management
 
1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections
 
## Core Principles

- **KISS (Keep It Simple Stupid)**: Always choose the simplest solution that works. Applies to code, architecture, communication, tooling — everything. If it feels complex, step back and simplify.
- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

## Project Architecture

This system converts Jira tickets into high-quality prompts for generating correct code changes.

### System Flow

Jira Ticket → Ticket Expansion → Embedding Generation → Vector Search → Graph Expansion → Ranking → Context Compression → Prompt Generation → Developer Prompt

### Core Components

- **API Layer** (`api/`): FastAPI. Receives Jira tickets, triggers retrieval, returns prompts.
- **Repository Indexing** (`indexing/`): Clones repo → parses files → extracts symbols → generates embeddings → builds code graph → stores metadata. Key modules: `symbol_extractor.py`, `embedding_pipeline.py`, `graph_builder.py`.
- **Vector Search**: Qdrant. Stores embeddings for functions, classes, methods, modules. Semantic retrieval.
- **Code Knowledge Graph**: Stores symbol relationships (calls, imports, inherits, references). Graph expansion retrieves related context.
- **Hybrid Retrieval**: Combines semantic vector search + keyword search + graph expansion, then ranks results.
- **Ranking Engine**: Ranks by semantic similarity, graph proximity, keyword relevance, git recency, symbol density.
- **Context Compression**: Extracts only relevant functions/classes to fit within LLM token limits (4000–6000 tokens).
- **Prompt Generation**: Structured output with task description, repo context, relevant files, code snippets, implementation instructions, constraints.
- **Workflow Orchestration**: LangGraph. Each pipeline stage is a graph node.

### Tech Stack

- **API**: FastAPI
- **Metadata DB**: PostgreSQL
- **Vector Storage**: Qdrant
- **Cache**: Redis
- **Orchestration**: LangGraph

### Design Principles

- Maintain modular architecture
- Avoid coupling indexing and retrieval logic
- Keep retrieval deterministic
- Prioritize retrieval accuracy
- Keep prompt generation simple and predictable
- The goal is accurate context generation, not code generation

## Engineering Rules

### Think Before Coding

1. Analyze the problem
2. Propose an approach
3. Identify edge cases
4. Define tests
5. Implement

### Test-Driven Development

1. Write failing tests first
2. Run tests (confirm failure)
3. Implement minimal code
4. Run tests (confirm pass)
5. Refactor

New features require tests. Bug fixes require regression tests.

### Code Quality Standards

- **DRY**: Extract reusable functions; no duplicated logic
- **SOLID**: Single responsibility, dependency inversion, open/closed
- **Small functions**: Single responsibility, ideally under ~30 lines
- **Explicit naming**: `payment_retry_attempts` not `tmp`; `calculate_order_total()` not `handler()`
- **Composition over inheritance**: Avoid deep hierarchies
- **No hidden side effects**: Prefer pure functions, return explicit result objects
- **File size**: Keep files under ~400 lines

### Architecture Patterns

- **Layered architecture**: `api/` → `services/` → `repositories/` → `models/` → `tests/`
- API never accesses repositories directly
- Services contain business logic and orchestrate repos + external APIs
- Repositories handle data access only (no business logic)
- **Dependency injection**: Pass dependencies as parameters, never hardcode clients
- **Result objects**: Return structured results (`success`, `retries`, `error`) instead of raw values

### Error Handling

- **Fail fast**: Never silently ignore errors. No bare `except: pass`.
- **Domain exceptions**: `PaymentError`, `GatewayTimeoutError` — avoid generic `Exception`
- **Logging**: Log external API calls, retries, DB writes, failures. Use structured logging.
- **Idempotent operations**: Operations must be safe to retry

### Configuration

- No hardcoded config values. Use environment variables (`DATABASE_URL`, `QDRANT_URL`, `REDIS_URL`)
- Configuration loader in `config/settings.py`

### Security

- Never expose secrets or log credentials
- Always validate external/user input

### Performance

- Avoid N+1 queries, loading entire datasets, inefficient loops
- Prefer batch operations