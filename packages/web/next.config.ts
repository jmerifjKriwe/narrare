import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./lib/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  // next@16.3.1 + @swc/helpers >=0.5.17: Node 24 require(esm) activates the
  // `module-sync` export condition at runtime, but Next's output-file tracing
  // resolves with classic require conditions, so only the cjs variants are
  // traced into .next/standalone and the server crashes on boot with
  // MODULE_NOT_FOUND for @swc/helpers/esm/*.js. Force-trace the esm tree until
  // a stable Next release fixes tracing; then DELETE this block and close
  // Q-020 (docs/architecture/questions/Q-020-swc-helpers-standalone-tracing.md).
  outputFileTracingIncludes: {
    "/**": ["../../node_modules/.pnpm/@swc+helpers@*/node_modules/@swc/helpers/esm/**"],
  },
  experimental: {
    // Proxy body-clone buffer (default 10MB) must stay >= the import API
    // total guard MAX_TOTAL_BYTES (25 MiB) + multipart envelope.
    // Coupling rule + evidence: ADR-091 Post-implementation Amendment.
    proxyClientMaxBodySize: "30mb",
  },
  typedRoutes: true,
  logging: {
    incomingRequests: {
      ignore: [/_next\/static/, /_next\/image/, /favicon/],
    },
    browserToTerminal: "warn",
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
