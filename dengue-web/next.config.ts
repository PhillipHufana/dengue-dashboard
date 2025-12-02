// next.config.mjs or next.config.ts (depending on your setup)
// If you're using `next.config.mjs`, drop the type and use JSDoc instead.

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typescript: {
    // WARNING: this hides type errors in builds; use only while you're iterating.
    ignoreBuildErrors: false,
  },
  images: {
    unoptimized: true,
  },
  // add any other options you need here later
};

export default nextConfig;
