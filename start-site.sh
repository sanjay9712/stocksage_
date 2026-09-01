#!/bin/bash
# ============================================================
# StockSage — Start site & get public URL (one command)
# Run: bash start-site.sh
# ============================================================

cd "$(dirname "$0")"

# Remove any config that could interfere with quick tunnel
[ -f ~/.cloudflared/config.yml ] && mv ~/.cloudflared/config.yml ~/.cloudflared/config.yml.bak 2>/dev/null

echo "=== Starting backend ==="
lsof -ti :8000 | xargs -r kill 2>/dev/null
sleep 1
cd backend
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "=== Waiting for backend ==="
sleep 4

echo "=== Starting frontend ==="
cd ../frontend
if [ -d ".next" ]; then
    nohup npx next start -p 3000 > /tmp/frontend.log 2>&1 &
else
    nohup npx next dev -p 3000 > /tmp/frontend.log 2>&1 &
fi
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo "=== Waiting for frontend ==="
sleep 5

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
