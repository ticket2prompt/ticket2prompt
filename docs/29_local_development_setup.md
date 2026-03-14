
# 29 Local Development Setup

This document describes how to run the entire system locally using open-source tools.

The development environment uses containerized services for infrastructure
components while the Python backend runs locally.

---

# Required Software

Install the following locally:

- Python 3.11+
- Docker
- Docker Compose
- Git

---

# Infrastructure Services

The system requires the following services:

Vector Database:
Qdrant

Metadata Database:
PostgreSQL

Cache:
Redis

---

# Docker Compose Setup

Create a `docker-compose.yml` file.

```yaml
version: "3.8"

services:

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: code_context
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
```

Run infrastructure:

```
docker compose up -d
```

---

# Python Environment

Create virtual environment.

```
python -m venv venv
source venv/bin/activate
```

Install dependencies.

```
pip install fastapi
pip install uvicorn
pip install qdrant-client
pip install psycopg2-binary
pip install redis
pip install tree-sitter
pip install sentence-transformers
pip install langgraph
```

---

# Environment Variables

Create `.env` file.

```
POSTGRES_URL=postgresql://dev:dev@localhost:5432/code_context
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
EMBEDDING_MODEL=bge-small-en
```

---

# Running the Backend

Start the API server.

```
uvicorn api.main:app --reload
```

API will run on:

```
http://localhost:8000
```

---

# Running Indexing

To index a repository:

```
python scripts/index_repository.py --repo https://github.com/example/project
```

This will:

1. Clone repository
2. Extract symbols
3. Generate embeddings
4. Store vectors
5. Build graph relationships

---

# Testing Retrieval

Example API request:

```
POST /jira/ticket
```

Body:

```
{
  "title": "Retry payment gateway failures",
  "description": "Add retry logic for failed stripe requests"
}
```

The system should return a generated Cursor prompt.

---

# Development Workflow

Typical development loop:

1. Start infrastructure containers
2. Run backend locally
3. Index repository
4. Send test Jira ticket
5. Inspect generated prompt
