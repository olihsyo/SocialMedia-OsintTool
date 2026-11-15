import json

# যেগুলো check_apis.py তে WORKING দেখিয়েছে
working_names = [
    "QuizGiri", "Shudokko", "Dhaka bank", "TheMallBD", 
    "Cinematic", "osudpotro", "BTCL BDIA", "BD Tickets", 
    "Swap.com.bd", "Fundesh", "AppLink", "GP Web Login", 
    "Deepto Play", "Sailor Clothing", "Osudpotro", 
    "PKLuck2 No Login", "GP Flexiplan", "GP FWA", "Priyoshikkhaloy"
]

with open('apis.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    apis = data.get('apis', [])

working_apis = [api for api in apis if api.get('name') in working_names]

with open('working_apis.json', 'w', encoding='utf-8') as f:
    json.dump({"apis": working_apis}, f, indent=2, ensure_ascii=False)

print(f"[+] Total {len(working_apis)} working APIs saved to working_apis.json")
