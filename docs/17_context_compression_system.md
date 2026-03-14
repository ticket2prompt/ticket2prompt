# 17 Context Compression System

This document defines how retrieved repository files are compressed into
LLM‑friendly context before prompt generation.

Large repositories may contain thousands of lines across the retrieved
files. Sending full files to the language model would exceed token
limits and introduce noise. Context compression selects only the most
relevant parts.

------------------------------------------------------------------------

# Objective

Transform retrieved files into a compact, structured context that:

-   fits inside LLM token limits
-   preserves important logic
-   removes unrelated code
-   keeps structural understanding of the system

------------------------------------------------------------------------

# Input

The context compression system receives:

-   ranked_files (8--12 files)
-   ranked_symbols
-   graph relationships
-   Jira ticket text

------------------------------------------------------------------------

# Token Budget

Typical safe token budget for context:

4000--6000 tokens

This budget includes:

-   code snippets
-   dependency explanations
-   repository context summary

------------------------------------------------------------------------

# Symbol Prioritization

Instead of including entire files, the system extracts only relevant
symbols.

Examples:

functions methods classes

Example:

processPayment() retryPayment()

Only the code block belonging to the symbol is extracted.

------------------------------------------------------------------------

# Graph Context Inclusion

For each selected symbol, include related symbols discovered during
graph expansion.

Example:

retryPayment → processPayment → stripeGateway

This preserves logical flow.

------------------------------------------------------------------------

# Context Ranking Inside Files

If a file contains many symbols, prioritize:

1.  symbols matched during vector search
2.  symbols discovered during graph expansion
3.  surrounding helper functions

Low‑relevance symbols are excluded.

------------------------------------------------------------------------

# Snippet Extraction

For each selected symbol include:

-   function signature
-   relevant code block
-   minimal surrounding context

Avoid including entire files.

------------------------------------------------------------------------

# Example Compression

Original file:

1200 lines

Extracted snippets:

processPayment() → 40 lines retryPayment() → 25 lines
handlePaymentError() → 20 lines

Total extracted:

\~85 lines

------------------------------------------------------------------------

# Repository Summary

Include a short repository context summary before code snippets.

Example:

The payment flow is:

checkoutController → orderService → paymentService → stripeGateway

This helps the model understand system architecture.

------------------------------------------------------------------------

# Deduplication

Sometimes multiple files include identical helper functions.

Duplicate snippets should be removed.

------------------------------------------------------------------------

# Ordering Strategy

Context ordering:

1.  repository architecture summary
2.  primary matched symbols
3.  graph‑expanded symbols
4.  supporting helpers

This improves reasoning for the LLM.

------------------------------------------------------------------------

# Safety Rules

Never include:

-   generated code
-   large dependency files
-   external libraries
-   minified code

------------------------------------------------------------------------

# Output Format

Compressed context should contain:

-   file paths
-   symbol names
-   extracted code blocks

Example:

File: src/services/paymentService.ts

Function: processPayment()

`<code snippet>`{=html}

------------------------------------------------------------------------

# Performance Considerations

Compression must run quickly.

Target runtime:

\< 200 ms

Strategies:

precompute symbol boundaries store line offsets during indexing avoid
reading full files when possible

------------------------------------------------------------------------

# Integration with Prompt Generator

The compressed context becomes the primary input to the prompt
generator.

Pipeline:

retrieval results → context compression → structured context → prompt
generation
