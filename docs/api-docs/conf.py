"""Sphinx configuration for Ticket to Prompt API documentation."""

import os
import sys

# Add project root to sys.path so autodoc can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

project = 'Ticket to Prompt'
copyright = '2026, Ticket to Prompt Authors'
version = '0.1.0'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinxcontrib.openapi',
    'myst_parser',
]

# Napoleon settings (Google style)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False

# autodoc settings
autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'show-inheritance': True,
    'member-order': 'bysource',
}
autodoc_typehints = 'description'

# Mock imports for modules that need external services
autodoc_mock_imports = [
    'psycopg2',
    'qdrant_client',
    'redis',
    'celery',
    'sentence_transformers',
    'tree_sitter',
    'tree_sitter_python',
    'tree_sitter_javascript',
    'tree_sitter_typescript',
    'tree_sitter_go',
    'tree_sitter_java',
    'tree_sitter_rust',
    'litellm',
    'git',
    'langgraph',
]

# sphinx-autodoc-typehints
always_document_param_types = True

# MyST parser for .md files
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# Theme
html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'navigation_depth': 3,
}

# Exclude patterns
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
