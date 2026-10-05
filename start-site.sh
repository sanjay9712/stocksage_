#!/bin/bash
# ============================================================
# StockSage — Start site & get public URL (one command)
# Run: bash start-site.sh
# ============================================================

cd "$(dirname "$0")"

# Remove any config that could interfere with quick tunnel
[ -f ~/.cloudflared/config.yml ] && mv ~/.cloudflared/config.yml ~/.cloudflared/config.yml.bak 2>/dev/null

echo "=== Starting backend ==="
# fuser, not lsof: lsof misses port holders in this WSL environment.
fuser -k 8000/tcp 2>/dev/null
sleep 1
cd backend
setsid nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 < /dev/null &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "=== Waiting for backend ==="
# Cold import of all providers takes 10-25s; wait for /health instead of a
# fixed sleep.
for i in $(seq 1 30); do
    curl -s -m 2 http://localhost:8000/health > /dev/null 2>&1 && break
    sleep 2
done

echo "=== Starting frontend ==="
fuser -k 3000/tcp 2>/dev/null
sleep 1
cd ../frontend
# Only serve a production build when one actually exists (.next/BUILD_ID).
# A dev-mode .next has no BUILD_ID and `next start` would crash.
if [ -f ".next/BUILD_ID" ]; then
    nohup npx next start -p 3000 > /tmp/frontend.log 2>&1 &
else
    nohup npx next dev -p 3000 > /tmp/frontend.log 2>&1 &
fi
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo "=== Waiting for frontend ==="
for i in $(seq 1 30); do
    curl -s -m 2 -o /dev/null http://localhost:3000 && break
    sleep 2
done

echo "=== Starting Cloudflare Tunnel ==="
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

nohup /tmp/cloudflared tunnel --url http://localhost:3000 > /tmp/cf-tunnel.log 2>&1 &
TUNNEL_PID=$!
echo "Tunnel PID: $TUNNEL_PID"

echo "=== Waiting for tunnel URL ==="
sleep 8

URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cf-tunnel.log | head -1)

echo ""
echo "============================================================"
echo "  YOUR SITE IS LIVE AT:"
echo ""
echo "  $URL"
echo ""
echo "  Login: test@test.com / testpass123"
echo "  Or register a new account at the URL."
echo "============================================================"
echo ""
echo "  Backend PID:  $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo "  Tunnel PID:   $TUNNEL_PID"
echo ""
echo "  To stop all:  kill $BACKEND_PID $FRONTEND_PID $TUNNEL_PID"
echo ""
