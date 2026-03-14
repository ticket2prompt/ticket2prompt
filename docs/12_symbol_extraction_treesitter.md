# 12 Symbol Extraction with Tree-sitter

This document defines how repository code is parsed and how symbols are
extracted. Symbol extraction is the foundation of the indexing pipeline.

The system uses Tree-sitter to build abstract syntax trees (AST) for
source files.

------------------------------------------------------------------------

# Why Tree-sitter

Tree-sitter is chosen because it:

-   supports many programming languages
-   produces accurate ASTs
-   works incrementally
-   is fast enough for large repositories

It allows precise extraction of:

-   functions
-   classes
-   methods
-   imports
-   call expressions

------------------------------------------------------------------------

# Supported Languages (Initial)

The system should support common backend and frontend languages.

Initial set:

-   TypeScript
-   JavaScript
-   Python
-   Go
-   Java

Additional languages can be added later.

------------------------------------------------------------------------

# Parsing Pipeline

For each repository file:

1.  detect language from extension
2.  load Tree-sitter parser for that language
3.  generate AST
4.  traverse AST nodes
5.  extract symbol information

------------------------------------------------------------------------

# Extracted Symbols

Symbols are structural units of code.

Types:

function class method module interface struct

Example:

function processPayment()

class PaymentService

method retryPayment()

------------------------------------------------------------------------

# Example Extraction

Source code:

class PaymentService {

processPayment(order) { chargeCustomer(order) }

retryPayment(order) { processPayment(order) }

}

Extracted symbols:

PaymentService (class) processPayment (method) retryPayment (method)

------------------------------------------------------------------------

# Symbol Metadata

Each extracted symbol must contain:

symbol_id symbol_name symbol_type file_path repo start_line end_line
language

Example:

symbol_id: sym_921 symbol_name: processPayment symbol_type: function
file_path: src/services/paymentService.ts start_line: 120 end_line: 185

------------------------------------------------------------------------

# Dependency Extraction

While parsing AST we also capture relationships.

Examples:

imports function calls class inheritance

Example:

retryPayment → processPayment

This relationship becomes a graph edge.

------------------------------------------------------------------------

# Graph Edge Example

from_symbol: retryPayment to_symbol: processPayment relation_type: calls

Stored in PostgreSQL graph table.

------------------------------------------------------------------------

# Handling Large Files

Some files contain thousands of lines.

Strategy:

-   extract only relevant symbol blocks
-   avoid embedding entire files
-   limit max symbol size

------------------------------------------------------------------------

# Ignored Files

Skip indexing for:

node_modules dist build vendor generated files

These directories contain compiled or external code.

------------------------------------------------------------------------

# Monorepo Considerations

Large monorepos may contain multiple services.

Strategy:

store module_path store repository_root store service_name if detectable

This allows filtering retrieval by service.

------------------------------------------------------------------------

# Incremental Symbol Updates

When repository changes:

1.  detect changed files
2.  re-parse those files only
3.  update symbol table
4.  update graph edges
5.  refresh embeddings

Full re-indexing is avoided.

------------------------------------------------------------------------

# Integration with Indexing Pipeline

Symbol extraction stage occurs after repository cloning.

Pipeline:

clone repo → file filtering → Tree-sitter parsing → symbol extraction →
embedding generation → graph construction

------------------------------------------------------------------------

# Performance Considerations

Typical repository:

10k files 50k symbols

Extraction time typically:

1--3 minutes on modern hardware.

Parallel parsing can further reduce indexing time.
