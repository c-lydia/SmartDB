#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-start}" = firmware ]; then
  cd esp_idf/smartdb_fusion
  exec ./setup.sh
fi
if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
  echo 'Install Node.js 22 LTS (with npm), then run this launcher again.' >&2; exit 1
fi
if ! command -v java >/dev/null; then
  echo 'Install Java 21 or newer for the Firestore emulator, then run this launcher again.' >&2; exit 1
fi
if [ ! -d node_modules ]; then npm ci; fi
case "${1:-start}" in
  start) npm run build; exec node tools/system.mjs ;;
  test) exec npm test ;;
  firmware) cd esp_idf/smartdb_fusion; exec ./setup.sh ;;
  *) echo 'Usage: sh system.sh [start|test|firmware]' >&2; exit 2 ;;
esac
