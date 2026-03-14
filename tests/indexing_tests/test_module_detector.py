"""Tests for indexing.module_detector module."""

import os
from unittest.mock import patch

import pytest

from indexing.module_detector import (
    DetectedModule,
    classify_file_to_module,
    detect_cross_module_dependencies,
    detect_modules,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_module(name: str, path: str, language=None, manifest_file=None) -> DetectedModule:
    return DetectedModule(name=name, path=path, language=language, manifest_file=manifest_file)


def _write_file(base, rel_path: str, content: str = "") -> None:
    """Create a file at base/rel_path, making parent dirs as needed."""
    full = base / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


# ---------------------------------------------------------------------------
# TestDetectModules
# ---------------------------------------------------------------------------

class TestDetectModules:
    def test_detects_python_modules_by_pyproject_toml(self, tmp_path):
        """A directory with pyproject.toml inside a service dir is detected."""
        _write_file(tmp_path, "services/payments/pyproject.toml", "[tool.poetry]")
        _write_file(tmp_path, "services/payments/src/handler.py", "")

        modules = detect_modules(str(tmp_path))

        names = [m.name for m in modules]
        assert "payments" in names

        payments = next(m for m in modules if m.name == "payments")
        assert payments.path == os.path.join("services", "payments")
        assert payments.language == "python"
        assert payments.manifest_file == "pyproject.toml"

    def test_detects_node_modules_by_package_json(self, tmp_path):
        """A directory with package.json inside a service dir is detected."""
        _write_file(tmp_path, "services/frontend/package.json", "{}")

        modules = detect_modules(str(tmp_path))

        names = [m.name for m in modules]
        assert "frontend" in names

        frontend = next(m for m in modules if m.name == "frontend")
        assert frontend.language == "typescript"
        assert frontend.manifest_file == "package.json"

    def test_detects_go_modules_by_go_mod(self, tmp_path):
        """A directory with go.mod inside a service dir is detected."""
        _write_file(tmp_path, "services/gateway/go.mod", "module gateway")

        modules = detect_modules(str(tmp_path))

        gateway = next((m for m in modules if m.name == "gateway"), None)
        assert gateway is not None
        assert gateway.language == "go"
        assert gateway.manifest_file == "go.mod"

    def test_detects_java_modules_by_build_gradle(self, tmp_path):
        """A directory with build.gradle inside a service dir is detected."""
        _write_file(tmp_path, "services/billing/build.gradle", "apply plugin: 'java'")

        modules = detect_modules(str(tmp_path))

        billing = next((m for m in modules if m.name == "billing"), None)
        assert billing is not None
        assert billing.language == "java"
        assert billing.manifest_file == "build.gradle"

    def test_detects_service_directories_without_manifest(self, tmp_path):
        """A direct child of a service dir is detected even without a manifest."""
        _write_file(tmp_path, "services/payments/src/handler.py", "")

        modules = detect_modules(str(tmp_path))

        names = [m.name for m in modules]
        assert "payments" in names

        payments = next(m for m in modules if m.name == "payments")
        assert payments.manifest_file is None
        assert payments.language is None

    def test_returns_single_root_for_flat_repo(self, tmp_path):
        """A flat repo with no service directories returns a single root module."""
        _write_file(tmp_path, "src/utils.py", "")
        _write_file(tmp_path, "src/main.py", "")

        modules = detect_modules(str(tmp_path))

        assert len(modules) == 1
        assert modules[0].name == ""
        assert modules[0].path == ""

    def test_excludes_node_modules_and_vendor(self, tmp_path):
        """node_modules and vendor directories are never reported as modules."""
        _write_file(tmp_path, "services/payments/src/handler.py", "")
        _write_file(tmp_path, "services/node_modules/lodash/index.js", "")
        _write_file(tmp_path, "services/vendor/lib/util.go", "")

        modules = detect_modules(str(tmp_path))

        names = [m.name for m in modules]
        assert "node_modules" not in names
        assert "vendor" not in names

    def test_nested_modules_detected(self, tmp_path):
        """services/payments/ with its own pyproject.toml is detected as a module."""
        _write_file(tmp_path, "services/payments/pyproject.toml", "[tool.poetry]")
        _write_file(tmp_path, "services/auth/pyproject.toml", "[tool.poetry]")

        modules = detect_modules(str(tmp_path))

        names = {m.name for m in modules}
        assert "payments" in names
        assert "auth" in names

    def test_top_level_lib_with_manifest_detected(self, tmp_path):
        """A top-level directory that directly contains a manifest is detected.

        e.g. libs/ with its own pyproject.toml (not a child's manifest).
        """
        _write_file(tmp_path, "libs/pyproject.toml", "[tool.poetry]")
        _write_file(tmp_path, "libs/src/utils.py", "")

        modules = detect_modules(str(tmp_path))

        names = [m.name for m in modules]
        assert "libs" in names

        libs = next(m for m in modules if m.name == "libs")
        assert libs.manifest_file == "pyproject.toml"
        assert libs.language == "python"


# ---------------------------------------------------------------------------
# TestClassifyFileToModule
# ---------------------------------------------------------------------------

class TestClassifyFileToModule:
    def test_file_in_service_dir_maps_to_module(self):
        """services/payments/src/handler.py maps to the 'payments' module."""
        modules = [
            _make_module("payments", os.path.join("services", "payments")),
            _make_module("auth", os.path.join("services", "auth")),
        ]

        result = classify_file_to_module(
            os.path.join("services", "payments", "src", "handler.py"),
            modules,
        )

        assert result == "payments"

    def test_file_in_root_maps_to_root_module(self):
        """src/utils.py maps to the root module (empty string) when no module matches."""
        modules = [
            _make_module("", ""),
        ]

        result = classify_file_to_module("src/utils.py", modules)

        assert result == ""

    def test_shared_lib_maps_to_libs_module(self):
        """libs/auth/src/verify.py maps to the 'auth' module."""
        modules = [
            _make_module("auth", os.path.join("libs", "auth")),
            _make_module("payments", os.path.join("services", "payments")),
        ]

        result = classify_file_to_module(
            os.path.join("libs", "auth", "src", "verify.py"),
            modules,
        )

        assert result == "auth"

    def test_longest_prefix_wins(self):
        """The most specific (longest) matching module path wins."""
        modules = [
            _make_module("services", "services"),
            _make_module("payments", os.path.join("services", "payments")),
        ]

        result = classify_file_to_module(
            os.path.join("services", "payments", "handler.py"),
            modules,
        )

        assert result == "payments"

    def test_no_matching_module_returns_empty_string(self):
        """A file that matches no module path returns empty string."""
        modules = [
            _make_module("payments", os.path.join("services", "payments")),
        ]

        result = classify_file_to_module("other/stuff/file.py", modules)

        assert result == ""


# ---------------------------------------------------------------------------
# TestCrossModuleDependencyDetection
# ---------------------------------------------------------------------------

class TestCrossModuleDependencyDetection:
    def test_import_across_modules_detected(self):
        """An edge from a symbol in 'payments' to one in 'auth' is detected."""
        symbols = [
            {"symbol_id": "sym_pay_1", "module": "payments"},
            {"symbol_id": "sym_auth_1", "module": "auth"},
        ]
        edges = [
            ("sym_pay_1", "sym_auth_1", "imports"),
        ]

        result = detect_cross_module_dependencies(symbols, edges)

        assert len(result) == 1
        dep = result[0]
        assert dep["from_module"] == "payments"
        assert dep["to_module"] == "auth"
        assert dep["from_symbol"] == "sym_pay_1"
        assert dep["to_symbol"] == "sym_auth_1"
        assert dep["relation_type"] == "imports"

    def test_same_module_import_not_flagged_as_cross(self):
        """An edge between two symbols in the same module is not included."""
        symbols = [
            {"symbol_id": "sym_pay_1", "module": "payments"},
            {"symbol_id": "sym_pay_2", "module": "payments"},
        ]
        edges = [
            ("sym_pay_1", "sym_pay_2", "calls"),
        ]

        result = detect_cross_module_dependencies(symbols, edges)

        assert result == []

    def test_multiple_cross_module_edges(self):
        """Multiple cross-module edges are all returned."""
        symbols = [
            {"symbol_id": "sym_a", "module": "moduleA"},
            {"symbol_id": "sym_b", "module": "moduleB"},
            {"symbol_id": "sym_c", "module": "moduleC"},
        ]
        edges = [
            ("sym_a", "sym_b", "calls"),
            ("sym_b", "sym_c", "imports"),
            ("sym_a", "sym_c", "references"),
        ]

        result = detect_cross_module_dependencies(symbols, edges)

        assert len(result) == 3

    def test_unknown_symbol_ids_skipped(self):
        """Edges referencing unknown symbol IDs are silently skipped."""
        symbols = [
            {"symbol_id": "sym_a", "module": "moduleA"},
        ]
        edges = [
            ("sym_a", "sym_unknown", "calls"),
        ]

        result = detect_cross_module_dependencies(symbols, edges)

        assert result == []

    def test_empty_edges_returns_empty(self):
        """No edges returns an empty list."""
        symbols = [
            {"symbol_id": "sym_a", "module": "moduleA"},
        ]

        result = detect_cross_module_dependencies(symbols, [])

        assert result == []
