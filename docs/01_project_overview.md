# Project Overview

## Goal
Build a system that converts Jira tickets into high‑quality prompts that developers can paste into Cursor to generate correct code changes.

The system will:
- Read Jira ticket descriptions
- Analyze the connected GitHub repository
- Retrieve relevant files and code symbols
- Analyze dependencies and recent changes
- Generate a structured Cursor prompt with the correct context

## Core Idea
Instead of generating code directly, the system generates **context‑aware prompts**.

Pipeline:

Jira Ticket → Context Builder → Code Retrieval → Graph Expansion → Git Delta Analysis → Prompt Generator → Cursor

## Key Principles

1. Context is more important than generation
2. Retrieval must be deterministic and explainable
3. System must rely on open source tools
4. Python ecosystem only
5. Symbol‑level indexing instead of file chunking