/** @type {import('next').NextConfig} */

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/* to the FastAPI backend at the server level (rewrites).
  // This is ~50x faster than a route handler in dev mode because it
  // doesn't invoke the React server runtime on every request.
  // The browser sends the Authorization header directly (apiFetch adds it
  // from localStorage), so the proxy just forwards the request.
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
