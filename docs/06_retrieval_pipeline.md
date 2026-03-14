# Retrieval Pipeline

## Step 1: Ticket Embedding

Embed Jira ticket description.

## Step 2: Query Expansion

Generate alternative queries:

payment retry
gateway retry
transaction failure retry

## Step 3: Vector Search

Search embeddings in Qdrant.

Return top symbols.

## Step 4: Symbol Aggregation

Group symbols by file.

## Step 5: Graph Expansion

Traverse dependency graph.

Include neighbor symbols.

## Step 6: Git Signals

Boost scores for:

recently modified files
frequently edited modules

## Step 7: Ranking

final_score =
semantic_score * 0.6 +
dependency_score * 0.25 +
git_recency * 0.15

Return top 8–12 files.