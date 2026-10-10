from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from web_sources import load_project_page

project = "SmartDB"
author = "SmartDB"
copyright = "2026, SmartDB"
release = "v2 bench"
extensions = ["myst_parser", "sphinxcontrib.mermaid"]
source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", ".vscode", "Thumbs.db", ".DS_Store"]
html_theme = "sphinx_rtd_theme"
html_title = "SmartDB documentation"
html_static_path = ["_static"]
html_logo = "_static/smartdb-logo.svg"
html_css_files = ["branding.css"]
html_js_files = ["diagrams.js"]
html_show_sourcelink = False
html_theme_options = {"navigation_depth": 3, "collapse_navigation": False}
myst_enable_extensions = ["amsmath", "dollarmath", "colon_fence"]
myst_heading_anchors = 6
myst_fence_as_directive = ["mermaid"]
mermaid_version = "12.1.0"
mermaid_init_config = {
    "startOnLoad": False,
    "securityLevel": "strict",
    "fontFamily": "Arial, sans-serif",
    "flowchart": {"useMaxWidth": True, "curve": "linear"},
    "sequence": {"useMaxWidth": True, "wrap": True},
}
mermaid_height = "auto"
mermaid_fullscreen = True
mermaid_include_zenuml = False


def setup(app):
    app.connect("source-read", load_project_page)
