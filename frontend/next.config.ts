import type { NextConfig } from "next";

const apiOrigin = (
  process.env.HOTCLAW_API_ORIGIN ??
  process.env.NEXT_PUBLIC_HOTCLAW_API_ORIGIN ??
  ""
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    if (!apiOrigin) {
      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
