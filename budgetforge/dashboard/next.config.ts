import type { NextConfig } from "next";

if (process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is required in production");
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8011";
    return [
      { source: "/api/:path*", destination: `${base}/api/:path*` },
      { source: "/health", destination: `${base}/health` },
      { source: "/proxy/:path*", destination: `${base}/proxy/:path*` },
    ];
  },
};

export default nextConfig;
