/** The browser talks to /api/*; Next forwards it to the FastAPI backend (no CORS needed in dev). */
const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";
export default {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/:path*` }];
  },
};
