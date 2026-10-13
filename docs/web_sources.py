"""Publish maintained repository guides without keeping separate web copies.

Sphinx reads the small page placeholders below; source-read substitutes the real guide
and registers it as a dependency. Relative links are resolved from the original file,
then mapped to website pages or Sphinx downloads, including assets outside docs/.
"""

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parent
PAGES = {
    "project": "README.md",
    "system/index": "cloud/README.md",
    "system/console": "dashboard/README.md",
    "firmware/index": "esp_idf/smartdb_fusion/README.md",
    "hardware/index": "smart_db_v2/README.md",
    "hardware/board": "smart_db_v2/smart_db/README.md",
    "api/index": "postman/documents/README.md",
    "backend/index": "backend/README.md",
    "firmware/legacy-camera": "esp_idf/esp32_cam/esp32_cam/README.md",
}
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\s)]+)(\))")


def web_text(text, original, page):
    mapping = {
        (ROOT / source).resolve(): DOCS / (docname + ".md") for docname, source in PAGES.items()
    }

    def replace(match):
        before, destination, after = match.groups()
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        target = (original.parent / unquote(parsed.path)).resolve()
        if not target.is_relative_to(ROOT):
            raise ValueError(f"Documentation link escapes repository: {original}: {destination}")
        if target.is_dir() and (target / "README.md").is_file():
            target = target / "README.md"
        if target in mapping:
            target = mapping[target]
            prefix = ""
        elif target.is_relative_to(DOCS) and target.suffix == ".md":
            prefix = ""
        else:
            # MyST's path scheme makes non-page links downloadable, even Markdown files.
            prefix = "" if before.startswith("!") else "path:"
        relative = Path(os.path.relpath(target, page.parent)).as_posix()
        fragment = "#" + parsed.fragment if parsed.fragment else ""
        return before + prefix + relative + fragment + after

    # Do not rewrite Markdown examples inside fenced code blocks.
    output = []
    fence = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            output.append(line)
        else:
            output.append(line if fence else LINK.sub(replace, line))
    return "".join(output)


def load_project_page(app, docname, source):
    page = DOCS / (docname + ".md")
    original = (ROOT / PAGES[docname]) if docname in PAGES else page
    if docname in PAGES:
        app.env.note_dependency(str(original))
        source[0] = original.read_text(encoding="utf-8")
    source[0] = web_text(source[0], original, page)
