"""Sphinx configuration for Domovoy documentation."""

import sys
from pathlib import Path

# Add project root to path for autodoc
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# -- Project information -----------------------------------------------------
project = "Domovoy"
copyright = "2026, cargsl"
author = "cargsl"
version = "0.8.3"
release = version

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

# Source file settings
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
exclude_patterns = []

# -- MyST-Parser configuration -----------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]
myst_heading_anchors = 3

# -- Autodoc configuration ---------------------------------------------------
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# -- Napoleon configuration (Google/NumPy style docstrings) ------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# -- Intersphinx configuration -----------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable/", None),
}

# -- HTML output configuration -----------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
html_title = "Domovoy"

# Furo theme options
html_theme_options = {
    "source_repository": "https://github.com/cargsl/domovoy",
    "source_branch": "master",
    "source_directory": "docs/source/",
}
