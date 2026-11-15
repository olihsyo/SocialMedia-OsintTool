#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

TARGET="${1:?usage: ./run.sh <email|phone> [flags]}"
shift || true

echo "[*] Starting scan for: $TARGET"

if [[ "$TARGET" == *"@"* ]]; then
  python3 py/enrich.py --email "$TARGET" > /dev/null 2>&1 || true
else
  python3 py/enrich.py --phone "$TARGET" > /dev/null 2>&1 || true
fi

go run ./cmd/osintx -t "$TARGET" "$@"
