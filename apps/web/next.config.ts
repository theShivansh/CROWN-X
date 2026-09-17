import type { NextConfig } from "next";

// Static export (ARCHITECTURE §8): the browser calls API Gateway directly, and Amplify serves `out/`.
// `trailingSlash` emits `app/index.html`, which any static host serves for `/app/` without rewrites.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
