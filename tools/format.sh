#!/bin/sh
# Format maintained application code; leave hardware archives and dependencies alone.
set -eu
cd "$(dirname "$0")/.."

case "${1:---check}" in
  --check)
    prettier_mode=--check
    ruff_mode=--check
    clang_mode='--dry-run --Werror'
    shell_mode=-d
    ;;
  --write)
    prettier_mode=--write
    ruff_mode=
    clang_mode=-i
    shell_mode=-w
    ;;
  *)
    echo 'Usage: sh tools/format.sh [--check|--write]' >&2
    exit 2
    ;;
esac

for tool in ruff clang-format shfmt; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing formatter: $tool. See README.md (Code style)." >&2
    exit 1
  fi
done
if [ ! -x node_modules/.bin/prettier ]; then
  echo 'Missing Prettier. Run npm ci first.' >&2
  exit 1
fi

node_modules/.bin/prettier "$prettier_mode" \
  .prettierrc.json package.json firebase.json \
  'cloud/**/*.js' 'cloud/**/*.mjs' 'cloud/*.json' \
  'dashboard/src/**/*.{js,jsx,css}' dashboard/index.html dashboard/package.json dashboard/vite.config.js \
  'tools/*.mjs' 'docs/_static/*.{js,css}'

# Unquoted mode variables intentionally expand to zero, one, or two arguments.
ruff format $ruff_mode backend docs/*.py esp_idf/smartdb_fusion/tools esp_idf/smartdb_fusion/test
ruff check backend docs/*.py esp_idf/smartdb_fusion/tools esp_idf/smartdb_fusion/test

clang-format $clang_mode \
  esp_idf/smartdb_fusion/main/*.c esp_idf/smartdb_fusion/main/*.h \
  esp_idf/smartdb_fusion/components/fusion_core/*.c \
  esp_idf/smartdb_fusion/components/fusion_core/include/*.h \
  esp_idf/smartdb_fusion/config/calibration.h \
  esp_idf/smartdb_fusion/config/project_config.h \
  esp_idf/smartdb_fusion/config/local_config.example.h \
  esp_idf/smartdb_fusion/test/*.c esp_idf/smartdb_fusion/test/stubs/*.h

shfmt -i 2 -ci "$shell_mode" system.sh tools/format.sh docs/*.sh \
  esp_idf/smartdb_fusion/setup.sh esp_idf/smartdb_fusion/tools/check.sh
