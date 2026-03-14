import math

import pytest

from indexing.embedding_pipeline import EmbeddingResult, format_symbol_text, generate_embeddings


def test_format_symbol_text_function():
    result = format_symbol_text("my_func", "function", "def my_func(): pass", "src/main.py")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "my_func" in result
    assert "function" in result


def test_format_symbol_text_class():
    result = format_symbol_text("MyClass", "class", "class MyClass: pass", "src/models.py")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "MyClass" in result
    assert "class" in result


def test_format_symbol_text_includes_file_path():
    file_path = "src/utils/helpers.py"
    result = format_symbol_text("helper_fn", "function", "def helper_fn(): pass", file_path)
    assert file_path in result


def test_embedding_result_dataclass():
    result = EmbeddingResult(symbol_id="abc", embedding=[0.1, 0.2])
    assert result.symbol_id == "abc"
    assert result.embedding == [0.1, 0.2]


@pytest.mark.slow
def test_generate_embeddings_single_symbol():
    symbols = [
        {
            "symbol_id": "sym1",
            "name": "hello",
            "type": "function",
            "source": "def hello(): pass",
            "file_path": "main.py",
        }
    ]
    results = generate_embeddings(symbols, model_name="all-MiniLM-L6-v2")
    assert len(results) == 1
    assert isinstance(results[0], EmbeddingResult)
    assert results[0].symbol_id == "sym1"
    assert isinstance(results[0].embedding, list)
    assert len(results[0].embedding) > 0
    assert all(isinstance(v, float) for v in results[0].embedding)


@pytest.mark.slow
def test_generate_embeddings_multiple_symbols():
    symbols = [
        {
            "symbol_id": "sym1",
            "name": "alpha",
            "type": "function",
            "source": "def alpha(): pass",
            "file_path": "a.py",
        },
        {
            "symbol_id": "sym2",
            "name": "beta",
            "type": "class",
            "source": "class Beta: pass",
            "file_path": "b.py",
        },
        {
            "symbol_id": "sym3",
            "name": "gamma",
            "type": "function",
            "source": "def gamma(): return 1",
            "file_path": "c.py",
        },
    ]
    results = generate_embeddings(symbols, model_name="all-MiniLM-L6-v2")
    assert len(results) == 3
    result_ids = {r.symbol_id for r in results}
    assert result_ids == {"sym1", "sym2", "sym3"}


def test_generate_embeddings_empty_list():
    results = generate_embeddings([], model_name="all-MiniLM-L6-v2")
    assert results == []


@pytest.mark.slow
def test_embedding_vectors_are_normalized():
    symbols = [
        {
            "symbol_id": "sym1",
            "name": "normalize_me",
            "type": "function",
            "source": "def normalize_me(): pass",
            "file_path": "main.py",
        }
    ]
    results = generate_embeddings(symbols, model_name="all-MiniLM-L6-v2")
    embedding = results[0].embedding
    norm = math.sqrt(sum(v * v for v in embedding))
    assert norm == pytest.approx(1.0, abs=0.1)


@pytest.mark.slow
def test_generate_embeddings_deterministic():
    symbol = {
        "symbol_id": "sym1",
        "name": "stable_func",
        "type": "function",
        "source": "def stable_func(): return 42",
        "file_path": "stable.py",
    }
    results_a = generate_embeddings([symbol], model_name="all-MiniLM-L6-v2")
    results_b = generate_embeddings([symbol], model_name="all-MiniLM-L6-v2")
    assert results_a[0].embedding == pytest.approx(results_b[0].embedding)


@pytest.mark.slow
def test_embedding_dimension_consistent():
    symbols = [
        {
            "symbol_id": "sym1",
            "name": "func_one",
            "type": "function",
            "source": "def func_one(): pass",
            "file_path": "one.py",
        },
        {
            "symbol_id": "sym2",
            "name": "func_two",
            "type": "function",
            "source": "def func_two(): return True",
            "file_path": "two.py",
        },
    ]
    results = generate_embeddings(symbols, model_name="all-MiniLM-L6-v2")
    assert len(results[0].embedding) == len(results[1].embedding)


@pytest.mark.slow
def test_generate_embeddings_batch_size():
    symbols = [
        {
            "symbol_id": f"sym{i}",
            "name": f"func_{i}",
            "type": "function",
            "source": f"def func_{i}(): pass",
            "file_path": f"file_{i}.py",
        }
        for i in range(5)
    ]
    results = generate_embeddings(symbols, model_name="all-MiniLM-L6-v2", batch_size=2)
    assert len(results) == 5
    result_ids = {r.symbol_id for r in results}
    assert result_ids == {f"sym{i}" for i in range(5)}
