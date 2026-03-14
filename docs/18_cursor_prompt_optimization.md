
# 18 Cursor Prompt Optimization Layer

This document defines how the final prompt is constructed for use inside
the Cursor editor. The prompt must provide the language model with clear
instructions, structured repository context, and constraints so that it
generates high‑quality code changes.

The system does not generate code directly. Instead it generates a **prompt
optimized for Cursor** that developers can paste into the editor.

---

# Goals

The prompt must:

- explain the Jira task clearly
- include relevant repository context
- provide necessary code snippets
- guide the model toward the correct implementation
- avoid hallucinations

---

# Prompt Structure

The prompt should follow a consistent structure.

1. Task Summary
2. Repository Context
3. Relevant Files
4. Code Snippets
5. Implementation Instructions
6. Constraints
7. Expected Behavior

---

# Task Summary

Explain the Jira ticket in clear technical language.

Example:

Task: Add retry logic for payment gateway failures when Stripe returns
HTTP 500 errors.

---

# Repository Context

Explain how the relevant components interact.

Example:

System Flow:

checkoutController → orderService → paymentService → stripeGateway

This helps the model understand the architecture.

---

# Relevant Files

List the files selected by the retrieval system.

Example:

Relevant files:

src/controllers/paymentController.ts
src/services/paymentService.ts
src/adapters/stripeGateway.ts

---

# Code Snippets

Include compressed code snippets extracted during context compression.

Example:

File: src/services/paymentService.ts

Function: processPayment()

<code snippet>

---

# Implementation Instructions

Provide high‑level instructions for implementing the change.

Example:

Modify processPayment() to retry gateway calls up to 3 times when a
temporary failure occurs.

Retry logic should:

- catch gateway errors
- retry with exponential backoff
- fail after max attempts

---

# Constraints

Prevent unsafe modifications.

Example:

Constraints:

- Do not change public APIs
- Follow existing error handling patterns
- Maintain current logging conventions
- Ensure backward compatibility

---

# Expected Behavior

Explain how the system should behave after the change.

Example:

Expected result:

When Stripe returns HTTP 500, the system retries the request up to
three times before failing.

---

# Example Prompt

You are working in a TypeScript backend service.

Task:
Add retry logic for Stripe payment failures.

Repository Context:
checkoutController → orderService → paymentService → stripeGateway

Relevant Files:
paymentService.ts
stripeGateway.ts

Implementation Instructions:
Modify processPayment() to retry gateway calls.

Constraints:
Do not change public APIs.

---

# Prompt Length

Target prompt length:

2000–4000 tokens

Large prompts may degrade performance.

---

# Prompt Safety

The prompt should discourage the model from:

- modifying unrelated files
- introducing new dependencies
- rewriting large sections of code

---

# Integration with Pipeline

Prompt generation occurs after context compression.

Pipeline:

retrieval
→ context compression
→ prompt assembly
→ deliver prompt to user
