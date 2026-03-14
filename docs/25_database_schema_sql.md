
# 25 Database Schema SQL

PostgreSQL schema for metadata and graph storage.

```sql
CREATE TABLE symbols (
    symbol_id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    file_path TEXT,
    repo TEXT,
    start_line INT,
    end_line INT
);

CREATE TABLE files (
    file_id SERIAL PRIMARY KEY,
    file_path TEXT,
    repo TEXT,
    last_modified TIMESTAMP,
    commit_count INT
);

CREATE TABLE graph_edges (
    id SERIAL PRIMARY KEY,
    from_symbol TEXT,
    to_symbol TEXT,
    relation_type TEXT
);

CREATE INDEX idx_symbols_repo ON symbols(repo);
CREATE INDEX idx_graph_from ON graph_edges(from_symbol);
```
