# Repository Indexing Pipeline

## Step 1: Clone Repository

Use GitPython to clone repository locally.

## Step 2: File Filtering

Ignore:

node_modules
dist
build
vendor
coverage

## Step 3: Code Parsing

Use Tree-sitter to extract:

- functions
- classes
- methods
- imports
- inheritance
- calls

## Step 4: Symbol Creation

Each symbol stored as:

symbol_id
name
type
file_path
start_line
end_line
repo

## Step 5: Embedding Generation

Generate embeddings for:

- function bodies
- class definitions
- module summaries

Store embeddings in Qdrant.

## Step 6: Graph Construction

Edges:

calls
imports
inherits
references

Store graph edges in PostgreSQL.

## Step 7: Git Metadata

Store:

last_commit
author
commit_frequency
recent_changes