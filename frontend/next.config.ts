import type { NextConfig } from "next";

const localDevApiOrigin = "http://127.0.0.1:8000";

const apiOrigin = (
  process.env.HOTCLAW_API_ORIGIN ??
  process.env.NEXT_PUBLIC_HOTCLAW_API_ORIGIN ??
  (process.env.NODE_ENV === "production" ? "" : localDevApiOrigin)
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
