/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const backendUrl = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000/api/v1/:path*";
    const healthUrl = backendUrl.replace("/api/v1/:path*", "/health/:path*");
    return [
      {
        source: "/api/v1/:path*",
        destination: backendUrl,
      },
      {
        source: "/health/:path*",
        destination: healthUrl,
      },
    ];
  },
};

export default nextConfig;
