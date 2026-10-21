import type { NextConfig } from "next";

// One origin in the browser: the shell forwards /api to the FastAPI process.
// agentRules stays off: this project keeps one instruction file at the repo root.
const config: NextConfig = {
  agentRules: false,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default config;
