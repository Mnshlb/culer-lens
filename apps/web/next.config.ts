import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Docker image ships the self-contained server; local `next start` keeps the default output.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
};

export default nextConfig;
