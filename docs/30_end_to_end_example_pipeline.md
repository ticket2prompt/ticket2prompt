
# 30 End-to-End Example Pipeline

This document demonstrates a complete example of the system processing a Jira ticket
from input to final prompt generation.

---

# Step 1 — Jira Ticket

Example ticket:

Title:
Retry payment gateway failures

Description:
When Stripe returns a temporary error, retry the request before failing.

---

# Step 2 — Ticket Expansion

System generates multiple queries.

retry payment gateway
retry stripe failure
retry payment transaction
handle payment error

---

# Step 3 — Embedding Generation

Each query is embedded using the configured embedding model.

Example model:

bge-small-en

Embeddings are used for vector search.

---

# Step 4 — Vector Search

Query vectors are sent to the vector database.

Results:

processPayment()
retryPayment()
handlePaymentError()

---

# Step 5 — Graph Expansion

Dependency graph adds related symbols.

processPayment → stripeGateway
processPayment → paymentController

---

# Step 6 — Ranking

Files are ranked using:

semantic similarity
graph proximity
keyword matches
git recency

Example ranked files:

paymentService.ts
retryHandler.ts
stripeGateway.ts
paymentController.ts

---

# Step 7 — Context Compression

Extract relevant snippets.

Example snippets:

processPayment()
retryPayment()

Large files are reduced to only relevant functions.

---

# Step 8 — Prompt Assembly

Final prompt structure:

Task:
Add retry logic for Stripe failures.

Repository Context:
checkoutController → orderService → paymentService → stripeGateway

Relevant Files:
paymentService.ts
stripeGateway.ts

Code Snippets:
<function snippets>

Implementation Instructions:
Retry gateway calls up to 3 times with exponential backoff.

Constraints:
Do not modify public APIs.

---

# Step 9 — Prompt Output

The generated prompt is returned to the developer.

Developer pastes the prompt into Cursor to generate code.

---

# Pipeline Summary

Jira Ticket
→ Ticket Expansion
→ Embedding Generation
→ Vector Search
→ Graph Expansion
→ Ranking
→ Context Compression
→ Prompt Generation
→ Cursor Prompt
