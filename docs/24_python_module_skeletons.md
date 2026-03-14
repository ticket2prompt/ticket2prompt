
# 24 Python Module Skeletons

Example skeletons for core modules.

## repo_cloner.py

```python
from git import Repo

def clone_repo(repo_url: str, target_path: str):
    Repo.clone_from(repo_url, target_path)
```

## symbol_extractor.py

```python
def extract_symbols(file_path: str):
    # parse AST using tree-sitter
    return []
```

## vector_search.py

```python
def search_vectors(query_embedding, top_k=20):
    # query Qdrant
    pass
```

## ranking_engine.py

```python
def rank_files(candidate_files):
    # combine semantic + graph + keyword signals
    pass
```

## prompt_generator.py

```python
def build_prompt(ticket, context):
    return f"Task: {ticket}\nContext:\n{context}"
```
