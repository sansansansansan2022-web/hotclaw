import type { NextConfig } from "next";

const localDevApiOrigin = "http://127.0.0.1:8000";

const apiOrigin = (
  process.env.HOTCLAW_API_ORIGIN ??
  process.env.NEXT_PUBLIC_HOTCLAW_API_ORIGIN ??
  (process.env.NODE_ENV === "production" ? "" : localDevApiOrigin)
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  outputFileTracingRoot: process.cwd(),
  experimental: {
    cpus: 1,
    webpackBuildWorker: false,
  },
  // On this Windows dev machine, Next's built-in type-check worker can fail
  // with spawn EPERM after a successful compile. We keep type safety by
  // running `tsc --noEmit` explicitly in the startup script and let the
  // production build focus on emitting a complete `.next` output.
  typescript: {
    ignoreBuildErrors: true,
  },
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
