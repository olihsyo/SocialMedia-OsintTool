import aiohttp
import asyncio

def parse_proxies(filename):
    proxies = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                
                parts = line.split(':')
                if len(parts) == 2:
                    # format: ip:port
                    proxies.append(f"http://{parts[0]}:{parts[1]}")
                elif len(parts) == 4:
                    # format: ip:port:user:pass
                    proxies.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
    except FileNotFoundError:
        print(f"[-] File {filename} not found.")
    return proxies

async def test_proxy(session, proxy):
    try:
        # Using ipify to check if proxy works
        async with session.get('http://api.ipify.org?format=json', proxy=proxy, timeout=aiohttp.ClientTimeout(total=8)) as res:
            if res.status == 200:
                return proxy
    except:
        return None

async def main():
    proxies = parse_proxies('Proxy_YM.txt')
    print(f"[*] Loaded {len(proxies)} proxies from list.")
    
    if not proxies:
        return

    working = []
    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    
    print("[*] Testing proxies (this may take a minute)...")
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [test_proxy(session, p) for p in proxies]
        results = await asyncio.gather(*tasks)
        
        for r in results:
            if r:
                working.append(r)
                print(f"[+] Working: {r}")
                
    with open('working_proxies.txt', 'w') as f:
        for p in working:
            f.write(p + '\n')
            
    print(f"\n[*] Done. {len(working)} working proxies saved to 'working_proxies.txt'.")

if __name__ == '__main__':
    asyncio.run(main())
