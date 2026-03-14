
# 22 Evaluation & Retrieval Quality Metrics

This document defines how to evaluate the effectiveness of the Jira → Context → Cursor
system. Without proper evaluation metrics, it is impossible to know whether the
retrieval pipeline and prompt generation actually improve developer productivity.

The evaluation framework focuses on measuring retrieval accuracy, context usefulness,
and prompt effectiveness.

---

# Evaluation Goals

The system must answer three key questions:

1. Did the system retrieve the correct files?
2. Did the system include the correct code context?
3. Did the generated prompt help produce the correct implementation?

Each question is evaluated using different metrics.

---

# Retrieval Accuracy

The first evaluation step measures whether the system retrieves the correct files
for a given Jira ticket.

Example:

Ticket:
Add retry logic for payment gateway failures.

Expected files:

paymentService.ts
retryHandler.ts
stripeGateway.ts

If the retrieval engine returns these files, retrieval is considered successful.

---

# Precision

Precision measures how many retrieved files are actually relevant.

Formula:

precision = relevant_files / retrieved_files

Example:

Retrieved files = 10
Relevant files = 7

Precision = 0.70

Higher precision means less noise in the prompt.

---

# Recall

Recall measures whether the system retrieved all relevant files.

Formula:

recall = relevant_files_found / total_relevant_files

Example:

Total relevant files = 5
Retrieved relevant files = 4

Recall = 0.80

High recall ensures important context is not missed.

---

# Top-K Accuracy

Top-K accuracy measures whether the correct files appear in the top results.

Example:

Top 5 retrieved files contain at least one correct file.

Metrics commonly used:

Top-3 accuracy
Top-5 accuracy
Top-10 accuracy

---

# Context Quality

Even if the correct file is retrieved, the wrong code section may be included.

Evaluate:

- correct function included
- correct class included
- minimal irrelevant code

Human reviewers can score context quality.

Score range:

0–5

---

# Prompt Effectiveness

The final prompt should help the LLM produce a correct implementation.

Evaluation method:

1. provide generated prompt to model
2. generate code
3. compare with expected implementation

Score categories:

correct solution
partially correct
incorrect

---

# Test Dataset

Create a dataset of real historical tickets.

For each ticket record:

ticket_text
expected_files
expected_symbols
expected_behavior

Example dataset size:

50–200 tickets

---

# Automated Regression Testing

When retrieval logic changes, run evaluation against the dataset.

Compare:

precision
recall
Top-K accuracy

If metrics drop, the change introduced a regression.

---

# Logging Metrics

Each pipeline execution should log:

ticket_id
retrieved_files
final_ranked_files
execution_time

These logs help monitor production performance.

---

# Continuous Improvement

Evaluation results guide system improvements.

Possible improvements:

better embeddings
improved ranking weights
better query expansion
better context compression

---

# Target Benchmarks

Recommended initial targets:

Precision > 0.70
Recall > 0.75
Top-5 accuracy > 0.85

These benchmarks indicate useful retrieval performance.

---

# Integration with Development

Evaluation tests should run as part of CI pipelines.

Pipeline:

code change
→ run retrieval tests
→ compare metrics
→ approve or reject change
