#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
    .venv/bin/python docs/prepare_vercel.py
else
    python3 docs/prepare_vercel.py
fi
cd docs/_build/smartdb-docs
exec vercel deploy --prebuilt --prod "$@"
