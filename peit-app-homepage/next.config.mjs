/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Turbopack resolver aliases for browser compatibility
  // sql.js (used by @ngageoint/geopackage) tries to require Node.js 'fs' module
  turbopack: {
    resolveAlias: {
      fs: { browser: './lib/empty-module.js' },
      path: { browser: './lib/empty-module.js' },
      crypto: { browser: './lib/empty-module.js' },
    },
  },
  webpack: (config, { isServer }) => {
    // sql.js (used by @ngageoint/geopackage) tries to require 'fs' on Node
    // This tells webpack to treat 'fs' as an empty module in the browser
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      }
    }
    return config
  },
}

export default nextConfig
