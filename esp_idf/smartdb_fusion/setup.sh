#!/bin/sh
set -eu
cd "$(dirname "$0")"
# PlatformIO already includes pySerial; no extra terminal UI packages are needed.
if [ -x "$HOME/.platformio/penv/bin/python" ]; then
  exec "$HOME/.platformio/penv/bin/python" tools/setup.py "$@"
fi
exec python3 tools/setup.py "$@"
