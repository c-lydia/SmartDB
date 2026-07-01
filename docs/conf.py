from __future__ import annotations

from pathlib import Path

project = "SmartDB"
copyright = "2026, SmartDB"
author = "SmartDB"

extensions = ["myst_parser"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

myst_enable_extensions = [
    "amsmath",
    "dollarmath",
    "colon_fence",
]
myst_heading_anchors = 3

root = Path(__file__).resolve().parent
