# Phase 10 — Monorepo and Advanced Features

## Stream 1: Module Detection
- [ ] Tests: `tests/indexing_tests/test_module_detector.py`
- [ ] Implementation: `indexing/module_detector.py`

## Stream 2: Schema & Storage Changes
- [ ] Schema migration: add `module` column to `symbols`
- [ ] Extend `storage/postgres.py` with module-aware methods
- [ ] Extend `storage/qdrant_client.py` with `delete_by_module`
- [ ] Tests for schema and postgres changes

## Stream 3: Service-Level Index Namespacing
- [ ] Add `module` field to `TicketInput` and `SymbolMatch` in `retrieval/__init__.py`
- [ ] Add module filter to `retrieval/vector_search.py`
- [ ] Add module to payloads in `git_analysis/commit_analyzer.py`
- [ ] Tests: `tests/retrieval_tests/test_module_scoped_retrieval.py`
- [ ] Tests: extend `tests/retrieval_tests/test_vector_search.py`

## Stream 4: Monorepo Indexer
- [ ] Tests: `tests/indexing_tests/test_monorepo_indexer.py`
- [ ] Implementation: `indexing/monorepo_indexer.py`

## Stream 5: Webhook Handlers
- [ ] Add `github_webhook_secret` to `config/settings.py`
- [ ] Tests: `tests/integration_tests/test_webhook_handlers.py`
- [ ] Implementation: `integrations/webhook_handlers.py`
- [ ] Register webhook router in `api/main.py`

## Final
- [ ] Run full test suite
- [ ] Update README.md Phase 10 checkboxes
