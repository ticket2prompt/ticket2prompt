import os

import pytest

from indexing.file_filter import (
    DEFAULT_IGNORE_DIRS,
    DEFAULT_IGNORE_EXTENSIONS,
    LANGUAGE_EXTENSIONS,
    detect_language,
    filter_files,
    should_index_file,
)


def test_default_ignore_dirs_contains_expected():
    assert "node_modules" in DEFAULT_IGNORE_DIRS
    assert "dist" in DEFAULT_IGNORE_DIRS
    assert "build" in DEFAULT_IGNORE_DIRS
    assert "vendor" in DEFAULT_IGNORE_DIRS
    assert "coverage" in DEFAULT_IGNORE_DIRS


def test_default_ignore_extensions_contains_expected():
    assert ".pyc" in DEFAULT_IGNORE_EXTENSIONS
    assert ".so" in DEFAULT_IGNORE_EXTENSIONS
    assert ".class" in DEFAULT_IGNORE_EXTENSIONS


def test_language_extensions_python():
    assert LANGUAGE_EXTENSIONS[".py"] == "python"


def test_language_extensions_typescript():
    assert LANGUAGE_EXTENSIONS[".ts"] == "typescript"


def test_detect_language_python():
    assert detect_language("src/main.py") == "python"


def test_detect_language_unknown():
    assert detect_language("README.md") is None


def test_should_index_python_file():
    assert should_index_file("src/main.py") is True


def test_should_not_index_node_modules():
    assert should_index_file("node_modules/lodash/index.js") is False


def test_should_not_index_dist():
    assert should_index_file("dist/bundle.js") is False


def test_should_not_index_build():
    assert should_index_file("build/output.js") is False


def test_should_not_index_pyc():
    assert should_index_file("src/__pycache__/main.cpython-311.pyc") is False


def test_should_not_index_compiled():
    assert should_index_file("lib/module.so") is False


def test_should_index_with_custom_ignore():
    assert should_index_file("custom_dir/main.py", ignore_dirs={"custom_dir"}) is False


def test_filter_files_basic(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main")
    (tmp_path / "src" / "utils.py").write_text("# utils")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("// pkg")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "bundle.js").write_text("// bundle")
    (tmp_path / "README.md").write_text("# readme")

    result = filter_files(str(tmp_path))

    assert sorted(result) == ["src/main.py", "src/utils.py"]


def test_filter_files_empty_dir(tmp_path):
    result = filter_files(str(tmp_path))
    assert result == []


def test_filter_files_nested_structure(tmp_path):
    (tmp_path / "services" / "payments").mkdir(parents=True)
    (tmp_path / "services" / "payments" / "handler.py").write_text("# handler")
    (tmp_path / "services" / "payments" / "__pycache__").mkdir()
    (tmp_path / "services" / "payments" / "__pycache__" / "handler.cpython-311.pyc").write_bytes(b"")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "utils.go").write_text("package lib")

    result = sorted(filter_files(str(tmp_path)))

    assert "services/payments/handler.py" in result
    assert "lib/utils.go" in result
    assert not any("pyc" in p for p in result)
    assert not any("__pycache__" in p for p in result)
