#!/usr/bin/env bash
set -e
PORT="${PORT:-9090}"
touch hits.log
if ss -ltn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
  echo "[*] port $PORT busy — killing old collector"
  pkill -9 -f collector.py || true
  sleep 1
fi
PORT="$PORT" python3 collector.py &
COLL=$!
sleep 1
if ! kill -0 "$COLL" 2>/dev/null; then
  echo "[!] collector failed"
  exit 1
fi
echo "[*] collector pid=$COLL port=$PORT — log: $(pwd)/hits.log"
echo "[*] tunnel: ngrok http $PORT --log=stdout"
tail -f hits.log
