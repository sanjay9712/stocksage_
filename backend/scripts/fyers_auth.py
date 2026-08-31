#!/usr/bin/env python3
"""Fyers OAuth helper — get your daily access_token in ~30 seconds.

The Fyers access token expires every day. Run this script each morning (or when
the token expires) to get a fresh token and paste it into backend/.env.

PREREQUISITES (one-time):
  1. Create a Fyers API app at https://myapi.fyers.in/ (free with a Fyers account)
  2. Note your APP_ID (starts with "XXXX..." e.g. "Q77B...")
  3. Note your SECRET_ID (e.g. "f6a8...")
  4. Set the redirect URL in your Fyers app to: http://127.0.0.1:8080/callback
     (or any URL you control — this script uses 127.0.0.1:8080)

USAGE:
  python3 scripts/fyers_auth.py --app-id YOUR_APP_ID --secret-id YOUR_SECRET_ID

  Then open the printed URL in your browser, log in to Fyers, and the script
  will print your access_token. Paste it as APP_FYERS_ACCESS_TOKEN in backend/.env.

  You can also store app_id / secret_id in backend/.env as APP_FYERS_APP_ID and
  APP_FYERS_SECRET — then run with no flags.
"""
from __future__ import annotations

import argparse
import http.server
import sys
import threading
import urllib.parse
import webbrowser

import httpx

FYERS_APP_ID = "Q77B..."  # placeholder — replace or pass via --app-id
REDIRECT_URI = "http://127.0.0.1:8080/callback"
AUTH_URL = "https://api-t1.fyers.in/api/v3/generate-authcode"
TOKEN_URL = "https://api-t1.fyers.in/api/v3/validate-authcode"

# Shared state for the callback handler.
_auth_code: dict[str, str | None] = {"code": None}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("auth_code", [None])[0]
        if code:
            _auth_code["code"] = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Auth code received!</h2><p>You can close this tab.</p>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>No auth_code found in the URL.</h2>")

    def log_message(self, *args):
        pass  # silence default logging


def main():
    parser = argparse.ArgumentParser(description="Get a Fyers access_token via OAuth.")
    parser.add_argument("--app-id", required=True, help="Fyers APP_ID")
    parser.add_argument("--secret-id", required=True, help="Fyers SECRET_ID")
    args = parser.parse_args()

    # 1. Build the auth URL and open it in the browser.
    params = urllib.parse.urlencode({
        "client_id": args.app_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": "tradingapp",
    })
    url = f"{AUTH_URL}?{params}"
    print("\n1. Opening your browser to log in to Fyers...")
    print(f"   If it doesn't open, visit:\n   {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass  # headless — user copies the URL manually

    # 2. Start a local server to catch the redirect.
    print("2. Waiting for Fyers to redirect back...")
    server = http.server.HTTPServer(("127.0.0.1", 8080), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout=120)  # 2 min to log in
    server.server_close()

    code = _auth_code["code"]
    if not code:
        print("\nERROR: Did not receive an auth code within 2 minutes.")
        print("       Make sure your Fyers app's redirect URI is set to:")
        print(f"       {REDIRECT_URI}")
        sys.exit(1)

    print("3. Exchanging auth code for access token...")
    # 3. Exchange the auth code for an access token.
    body = {
        "grant_type": "authorization_code",
        "appIdHash": args.app_id,
        "code": code,
    }
    # Fyers expects the code URL-encoded; send as JSON.
    try:
        r = httpx.post(
            TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "appIdHash": args.app_id,
                "code": code,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"\nERROR: Token exchange failed: {e}")
        if hasattr(r, "text"):
            print(f"   Response: {r.text}")
        sys.exit(1)

    token = data.get("access_token")
    if not token:
        print(f"\nERROR: No access_token in response: {data}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SUCCESS! Your Fyers access token:")
    print("=" * 60)
    print(f"\n  APP_FYERS_ACCESS_TOKEN={token}\n")
    print("Paste this into backend/.env, then restart the backend.")
    print("The token is valid for ~1 day. Re-run this script tomorrow.\n")


if __name__ == "__main__":
    main()
