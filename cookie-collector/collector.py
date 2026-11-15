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
