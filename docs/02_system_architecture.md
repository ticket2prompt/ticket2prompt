# System Architecture

## High Level Pipeline

Jira Ticket
↓
Ticket Interpreter
↓
Context Retrieval Engine
↓
Vector Search
↓
Code Knowledge Graph Expansion
↓
Git Delta Analyzer
↓
Prompt Generator
↓
Cursor Prompt

## Core Modules

1. API Service
2. Repository Indexer
3. Symbol Extraction Engine
4. Vector Search Service
5. Code Knowledge Graph
6. Retrieval Ranking Engine
7. Git Delta Analyzer
8. Prompt Generation Engine

## Architecture Diagram

Frontend / CLI
      |
      v
FastAPI Backend
      |
      v
Retrieval Engine
      |
      v
Vector DB + Graph DB + Git Metadata