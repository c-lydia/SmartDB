# Documentation website

The website uses Sphinx, MyST Markdown and the Read the Docs theme. From the repository
root, run `./docs/build.sh`, then open `docs/_build/html/index.html` in a browser. The build
treats warnings as errors. Generated HTML is ignored by Git.

The existing repository `.venv` contains the required tools. For a fresh checkout, create
a Python environment and install `docs/requirements.txt` before building. The shell launcher
uses `.venv/bin/python` when available, otherwise `python3` from PATH.

`docs/index.md` owns the landing page and sidebar navigation. `docs/web_sources.py` maps
the firmware, hardware, Postman and backend web pages to their maintained repository
READMEs. Edit those originals; the page placeholders do not contain duplicate content.
Each build reads the originals, maps documentation links to rendered pages, and packages
linked supporting files as downloads. The firmware web page therefore stays aligned with
`esp_idf/smartdb_fusion/README.md` after rebuilding.

`docs/code/` contains the firmware module guide and source-backed C/protocol listings.
Its `literalinclude` directives read checked-in source directly on every build.
`docs/api/http.md`, `usb.md` and `telemetry.md` describe the implemented board interfaces
and the separate central API boundary. Keep them aligned with firmware and `postman/specs`.
`docs/related/bytelab.md` describes the related desktop workspace and current integration
limits. It is maintained here so a SmartDB checkout can build the website without a sibling
ByteLab checkout; review it against ByteLab when integration changes.

## Publish to Vercel

`./docs/build.sh` builds a local preview only. To build and publish the documentation to
Vercel, run from the repository root:

```sh
sh docs/deploy-vercel.sh
```

The launcher uses the globally installed Vercel CLI (verified with 63.1.2).
Install it with `npm install --global vercel@latest` if needed, and sign in once with
`vercel login`. On
the first deployment, choose the intended account and create or link the `smartdb-docs`
project. Subsequent deployments reuse its local project link.

The script builds a fresh Sphinx site and prepares Vercel's
[Build Output API](https://vercel.com/docs/build-output-api/configuration) artifact in
`docs/_build/smartdb-docs/.vercel/output`. It uploads the rendered pages, assets and explicitly
linked downloads, including source and PCB files. Build caches and private setup profiles
are not part of the artifact. The repository itself is not uploaded by this command.
The `.vercel/project.json` link remains inside the ignored build directory.

This project is intended to have a **public production domain without a password**.
Vercel preview/deployment URLs may have separate protection settings; share and verify the
production domain after deployment. The current public site is
[smartdb-docs.vercel.app](https://smartdb-docs.vercel.app).
This website does not expose or change board API
authentication. A build or upload alone does not establish that the public URL is live.

To prepare the artifact without uploading, run `.venv/bin/python docs/prepare_vercel.py`.
The existing documentation content and Sphinx navigation are retained; Vite is not needed
to host the static site on Vercel.

Deployment is manual through this launcher. The Vercel project's Git integration is
disconnected, so unrelated pushes to the SmartDB repository do not deploy this site.

## Architecture diagrams

Architecture pages use standard fenced `mermaid` blocks, so GitHub renders them too.
Sphinx enables the Mermaid directive through MyST and the pinned `sphinxcontrib-mermaid`
extension. Browser rendering uses Mermaid 12.1.0 from its pinned jsDelivr URL and provides
a fullscreen button for each diagram. Install `docs/requirements.txt` before building.

The current diagrams live in `system/architecture.md`; the full architecture specification
separately labels production targets and planned inference components. Update diagrams
when changing a transport, ownership boundary, command flow or protection transition.
Check both architecture pages in a browser after a clean build: each diagram must render
as SVG, without syntax-error panels. Avoid literal semicolons in sequence message labels,
which Mermaid treats as statement separators.
