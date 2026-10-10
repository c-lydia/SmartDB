#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 docs/prepare_hardware.py
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python -m sphinx -E -a -b html -W --keep-going docs docs/_build/html
fi
exec python3 -m sphinx -E -a -b html -W --keep-going docs docs/_build/html
