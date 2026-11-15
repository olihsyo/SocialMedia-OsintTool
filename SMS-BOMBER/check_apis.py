import asyncio
import aiohttp
import json
import random

with open('apis.json', 'r', encoding='utf-8') as f:
    apis = json.load(f).get('apis', [])

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36"
]

async def check_api(session, api):
    name = api.get('name', 'Unknown')
    url = api.get('url', '').replace('*****', '01700000000')
    method = api.get('method', 'get').lower()
    body_raw = api.get('body', '').replace('*****', '01700000000')
    headers = api.get('headers', {})
    headers['User-Agent'] = random.choice(USER_AGENTS)
    
    try:
        kwargs = {'timeout': aiohttp.ClientTimeout(total=10), 'ssl': False}
        if method == 'post':
            if 'application/json' in headers.get('content-type', ''):
                try: kwargs['json'] = json.loads(body_raw)
                except: kwargs['data'] = body_raw
            else:
                kwargs['data'] = body_raw
            async with session.post(url, headers=headers, **kwargs) as res:
                return name, res.status
        else:
            async with session.get(url, headers=headers, **kwargs) as res:
                return name, res.status
    except:
        return name, 'DEAD'

async def main():
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_api(session, api) for api in apis]
        results = await asyncio.gather(*tasks)
        
        working = []
        for name, status in results:
            if status in [200, 201, 202]:
                print(f"[+] WORKING: {name}")
                working.append(name)
            else:
                pass
                
        print(f"\nTotal Working APIs: {len(working)}")

if __name__ == '__main__':
    asyncio.run(main())
