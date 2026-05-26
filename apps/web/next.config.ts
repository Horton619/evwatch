import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const here = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.resolve(here, "..", "..");

const nextConfig: NextConfig = {
  // Monorepo: tell Next where the repo root is so file tracing follows
  // workspace packages and finds files outside apps/web/.
  outputFileTracingRoot: monorepoRoot,

  // Bring config/watchlist.yml into the serverless bundle. The dashboard's
  // "priority" quick filter reads it at runtime; without this include,
  // Vercel ships a function that can't see the file.
  outputFileTracingIncludes: {
    "/": ["../../config/watchlist.yml"],
  },
};

export default nextConfig;
