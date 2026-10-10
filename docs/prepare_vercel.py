#!/usr/bin/env python3
"""Build a clean documentation artifact for Vercel's Build Output API."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from prepare_hardware import prepare as prepare_hardware

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs/_build/smartdb-docs"


def main():
    prepare_hardware()
    SITE.mkdir(parents=True, exist_ok=True)
    # Build into a fresh directory so removed pages, old downloads and editor backups
    # from local previews cannot enter the public artifact.
    with tempfile.TemporaryDirectory(prefix="vercel-build-", dir=ROOT / "docs/_build") as tmp:
        temp = Path(tmp)
        html = temp / "static"
        subprocess.run([
            sys.executable, "-m", "sphinx", "-E", "-a", "-b", "html",
            "-W", "--keep-going", "-d", str(temp / "doctrees"),
            "-D", "html_copy_source=0", str(ROOT / "docs"), str(html),
        ], cwd=ROOT, check=True)
        (html / ".buildinfo").unlink(missing_ok=True)
        output = SITE / ".vercel/output"
        # Only replace our generated deployment output; retain the Vercel project link.
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        shutil.move(str(html), output / "static")
        (output / "config.json").write_text(json.dumps({
            "version": 3,
            "routes": [
                {"src": "/", "dest": "/index.html"},
                {"handle": "filesystem"},
            ],
        }, indent=2) + "\n")
    (SITE / "vercel.json").write_text(json.dumps({
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "framework": None,
    }, indent=2) + "\n")
    print(f"Vercel artifact ready: {SITE}")


if __name__ == "__main__":
    main()
