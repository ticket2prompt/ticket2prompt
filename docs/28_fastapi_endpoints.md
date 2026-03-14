
# 28 FastAPI Endpoints

Example API layer for triggering the pipeline.

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/jira/ticket")
def process_ticket(ticket: dict):
    # trigger retrieval workflow
    return {"status": "processing"}

@app.post("/repo/index")
def index_repository(repo_url: str):
    # start indexing job
    return {"status": "indexing_started"}

@app.get("/prompt/{ticket_id}")
def get_prompt(ticket_id: str):
    # return generated cursor prompt
    return {"prompt": "generated prompt here"}
```
