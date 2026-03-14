
# 26 Qdrant Collection Setup

Example Python setup for Qdrant vector collection.

```python
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance

client = QdrantClient(host="localhost", port=6333)

client.recreate_collection(
    collection_name="code_symbols",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
```

Example payload stored with vectors:

```
{
  "symbol_name": "processPayment",
  "file_path": "src/services/paymentService.ts",
  "repo": "orders-service",
  "language": "typescript"
}
```
