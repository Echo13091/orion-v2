/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backendInternalUrl =
      process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:5001";

    return [
      {
        source: "/orion-api/v1/:path*",
        destination: `${backendInternalUrl}/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
