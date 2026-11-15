১. PORT=9090 bash run.sh
২. আলাদা টার্মিনাল: ngrok http 9090 --log=stdout
৩. টানেল URL নিয়ে cookie_hook.js ও payload.html-এ বসাও
৪. টেস্ট: http://127.0.0.1:9000/payload.html
৫. tail -f hits.log
