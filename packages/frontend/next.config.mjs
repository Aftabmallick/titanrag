/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const rawBackend = process.env.BACKEND_INTERNAL_URL || (process.env.NODE_ENV === "production" ? "http://backend:8000" : "http://127.0.0.1:8000");
    const baseHost = rawBackend.replace(/\/api\/v1\/?$/, "").replace(/\/+$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${baseHost}/api/v1/:path*`,
      },
      {
        source: "/health/:path*",
        destination: `${baseHost}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
