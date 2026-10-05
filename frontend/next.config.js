/** @type {import('next').NextConfig} */

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/* to the FastAPI backend at the server level (rewrites).
  // This is ~50x faster than a route handler in dev mode because it
  // doesn't invoke the React server runtime on every request.
  // The browser sends the Authorization header directly (apiFetch adds it
  // from localStorage), so the proxy just forwards the request.
  //
  // NOTE: do NOT add a `websocket: true` field here — Next 14.2 rejects it
  // at config validation ("Invalid rewrite found") and refuses to boot.
  // The option only exists from Next 15. Dev-mode rewrites proxy WS
  // upgrades implicitly (the live-market stream works under `next dev`);
  // under a production build (`next build && next start`) the WS stream
  // won't tunnel until we either move to Next 15 or point the client at
  // the backend origin directly.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
